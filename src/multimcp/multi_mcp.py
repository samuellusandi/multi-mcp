import base64
import os
from contextlib import asynccontextmanager, AsyncExitStack

import uvicorn
import json
from typing import Literal, Any, Optional, AsyncIterator
from pydantic_settings import BaseSettings

from mcp.server.stdio import stdio_server
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.types import Receive, Scope, Send

from src.multimcp.mcp_client import MCPClientManager
from src.multimcp.mcp_proxy import MCPProxyServer
from src.utils.logger import configure_logging, get_logger

class MCPSettings(BaseSettings):
    """Configuration settings for the MultiMCP server."""
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    transport: Literal["stdio", "sse", "stream"] = "stdio"
    unify: bool = False
    sse_server_debug: bool = False
    config: str = "./mcp.json"
    basic_auth: str | None = None

class MultiMCP:

    def __init__(self, **settings: Any):
        self.settings = MCPSettings(**settings)
        configure_logging(level=self.settings.log_level)
        self.logger = get_logger("MultiMCP")
        self.proxy: Optional[MCPProxyServer] = None
        self.proxies: dict[str, MCPProxyServer] = {}
        self.client_managers: dict[str, MCPClientManager] = {}


    async def run(self):
        """Entry point to run the MultiMCP server: loads config, initializes clients, starts server."""
        self.logger.info(f"🚀 Starting MultiMCP with transport: {self.settings.transport}")
        config = self.load_mcp_config(path=self.settings.config)
        if not config:
            self.logger.error("❌ Failed to load MCP config.")
            return

        named_config = config.get("mcpServers", {})
        if not named_config:
            self.logger.error("❌ No 'mcpServers' key found in config.")
            return

        self.client_managers = {}
        total_clients = 0

        for name, server in named_config.items():
            self.client_managers[name] = MCPClientManager()
            clients = await self.client_managers[name].create_clients(name, server)

            if clients:
                total_clients += len(clients)
                self.logger.info(
                    f"✅ Connected {len(clients)} client(s) for configuration '{name}': {list(clients.keys())}")
            else:
                self.logger.warning(f"⚠️ No valid clients created for configuration '{name}'")

        if total_clients == 0:
            self.logger.error("❌ No valid clients were created across all configurations.")
            return

        if not self.settings.basic_auth:
            self.logger.warning("⚠️ No authentication string provided. Client connections will be unauthenticated.")

        self.logger.info(f"✅ Total connected clients: {total_clients}")

        try:
            self.proxies = {}
            for name, client_manager in self.client_managers.items():
                self.proxies[name] = await MCPProxyServer.create(client_manager)

            await self.start_server()
        finally:
            for manager in self.client_managers.values():
                await manager.close()


    def load_mcp_config(self,path="./mcp.json"):
        """Loads MCP JSON configuration From File."""
        if not os.path.exists(path):
            print(f"Error: {path} does not exist.")
            return None

        with open(path, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
                return data
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")
                return None


    async def start_server(self):
        """Start the proxy server in stdio or SSE mode."""
        self.logger.info(f"🚀 Starting MultiMCP with transport: {self.settings.transport}")
        if self.settings.transport == "stdio":
            await self.start_stdio_server()
        elif self.settings.transport == "sse":
            await self.start_sse_server()
        elif self.settings.transport == "stream":
            await self.start_stream_server()
        else:
            raise ValueError(f"Unsupported transport: {self.settings.transport}")

    async def start_stdio_server(self) -> None:
        """Run the proxy server over stdio."""
        async with stdio_server() as (read_stream, write_stream):
            await self.proxy.run(
                read_stream,
                write_stream,
                self.proxy.create_initialization_options(),
            )

    async def start_sse_server(self) -> None:
        """Run the proxy server over SSE transport."""
        base64_basic_auth = None
        if self.settings.basic_auth:
            self.logger.info(f"🔑 Enabling authentication with basic auth string: {self.settings.basic_auth}")
            base64_basic_auth = base64.b64encode(self.settings.basic_auth.encode("UTF-8")).decode()

        if base64_basic_auth:
            self.logger.info(f"🔑 Enabling authentication with basic auth string: {self.settings.basic_auth}")
            self.logger.info(f"🔑 Enabling authentication with base64 auth string: {base64_basic_auth}")

        url_prefix = f"/{base64_basic_auth}" if base64_basic_auth else ''
        sse = SseServerTransport(f"{url_prefix}/messages/")

        async def handle_sse(request):
            try:
                async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                    await self.proxy.run(
                        streams[0],
                        streams[1],
                        self.proxy.create_initialization_options(),
                    )
                return Response("", status_code=200)
            except Exception as e:
                self.logger.error(f"SSE connection error: {e}")
                return Response("SSE connection failed", status_code=500)

        starlette_app = Starlette(
            debug=self.settings.sse_server_debug,
            routes=[
                Route(f"{url_prefix}/sse", endpoint=handle_sse),
                Mount(f"{url_prefix}/messages/", app=sse.handle_post_message),

                # Dynamic endpoints
                Route(f"{url_prefix}/mcp_servers", endpoint=self.handle_mcp_servers, methods=["GET", "POST"]),
                Route(f"{url_prefix}/mcp_servers/{{name}}", endpoint=self.handle_mcp_servers, methods=["DELETE"]),
                Route(f"{url_prefix}/mcp_tools", endpoint=self.handle_mcp_tools, methods=["GET"])
            ],
        )

        config = uvicorn.Config(
            starlette_app,
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def start_stream_server(self) -> None:
        """Run the proxy server over Streamable HTTP transport."""
        base64_basic_auth = None
        if self.settings.basic_auth:
            self.logger.info(f"🔑 Enabling authentication with basic auth string: {self.settings.basic_auth}")
            base64_basic_auth = base64.b64encode(self.settings.basic_auth.encode("UTF-8")).decode()

        if base64_basic_auth:
            self.logger.info(f"🔑 Enabling authentication with basic auth string: {self.settings.basic_auth}")
            self.logger.info(f"🔑 Enabling authentication with base64 auth string: {base64_basic_auth}")

        url_prefix = f"/{base64_basic_auth}" if base64_basic_auth else ''

        session_managers = {}
        handle_functions = {}
        for name, proxy in self.proxies.items():
            print(name)
            session_managers[name] = StreamableHTTPSessionManager(
                app=proxy,
                event_store=None,
                json_response=True,
                stateless=True,
            )

            handle_functions[name] = \
                lambda scope, receive, send, captured_name=name: session_managers[captured_name].handle_request(scope, receive, send)

        @asynccontextmanager
        async def lifespan(app: Starlette) -> AsyncIterator[None]:
            """Context manager for session manager."""
            async with AsyncExitStack() as stack:
                for name, session_manager in session_managers.items():
                    handle_functions[name] = \
                        lambda scope, receive, send, captured_name=name: session_managers[captured_name].handle_request(scope, receive, send)
                    await stack.enter_async_context(session_manager.run())
                yield

        mounting_routes = []
        for name, handle_function in handle_functions.items():
            mounting_routes.append(Mount(f"{url_prefix}/{name}/mcp", app=handle_function))

        starlette_app = Starlette(
            debug=self.settings.sse_server_debug,
            routes=[
                *mounting_routes,

                # Dynamic endpoints
                Route(f"{url_prefix}/mcp_servers", endpoint=self.handle_mcp_servers, methods=["GET", "POST"]),
                Route(f"{url_prefix}/mcp_servers/{{name}}", endpoint=self.handle_mcp_servers, methods=["DELETE"]),
                Route(f"{url_prefix}/mcp_tools", endpoint=self.handle_mcp_tools, methods=["GET"]),
            ],
            lifespan=lifespan,
        )

        config = uvicorn.Config(
            starlette_app,
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def handle_mcp_servers(self, request: Request) -> JSONResponse:
        """Handle GET requests to list MCP clients at runtime."""
        method = request.method

        if method == "GET":
            servers = list(self.client_managers.keys())
            return JSONResponse({"active_servers": servers})

        return JSONResponse({"error": f"Unsupported method: {method}"}, status_code=405)

    async def handle_mcp_tools(self, request: Request) -> JSONResponse:
        """Return the list of currently available tools grouped by server."""
        try:
            if not self.proxies:
                return JSONResponse({"error": "Proxy not initialized"}, status_code=500)

            tools_by_server = {}
            for server_name, client in self.client_managers.items():
                try:
                    tools = await client.get_client(server_name).list_tools()
                    tools_by_server[server_name] = [tool.name for tool in tools.tools]
                except Exception as e:
                    tools_by_server[server_name] = f"❌ Error: {str(e)}"

            return JSONResponse({"tools": tools_by_server})

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
