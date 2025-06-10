import base64
import os
import uvicorn
import json
from typing import Literal,Any,Optional
from pydantic_settings import BaseSettings

from mcp.server.stdio import stdio_server
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from mcp.server.sse import SseServerTransport

from src.multimcp.mcp_client import MCPClientManager
from src.multimcp.mcp_proxy import MCPProxyServer
from src.utils.logger import configure_logging, get_logger

class PortHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add a header to the response to indicate the port the request was forwarded from."""

    def __init__(self, app, port: int):
        """Initialize the middleware with the port number."""
        super().__init__(app)
        self.port = str(port)

    async def dispatch(self, request: Request, call_next):
        """Dispatch the request to the next middleware or endpoint."""
        print(f"🔍 Middleware running for {request.url.path}")

        original_send = request._send

        async def custom_send(message):
            """Custom send function to add the header to the response."""
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append([b"x-forwarded-from", self.port.encode()])
                message["headers"] = headers
                print(f"✅ Added header x-forwarded-from: {self.port} to ASGI response")
            await original_send(message)

        request._send = custom_send

        response = await call_next(request)

        if hasattr(response, 'headers'):
            response.headers["X-Forwarded-From"] = self.port
            print(f"✅ Added header X-Forwarded-From: {self.port} to Response object")
            
        return response

class MCPSettings(BaseSettings):
    """Configuration settings for the MultiMCP server."""
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    transport: Literal["stdio", "sse"] = "stdio"
    sse_server_debug: bool = False
    config: str = "./mcp.json"
    basic_auth: str | None = None


class MultiMCP:

    def __init__(self, **settings: Any):
        self.settings = MCPSettings(**settings)
        configure_logging(level=self.settings.log_level)
        self.logger = get_logger("MultiMCP")
        self.proxy: Optional[MCPProxyServer] = None


    async def run(self):
        """Entry point to run the MultiMCP server: loads config, initializes clients, starts server."""
        self.logger.info(f"🚀 Starting MultiMCP with transport: {self.settings.transport}")
        config = self.load_mcp_config(path=self.settings.config)
        if not config:
            self.logger.error("❌ Failed to load MCP config.")
            return
        clients_manager = MCPClientManager()
        clients = await clients_manager.create_clients(config)
        if not clients:
            self.logger.error("❌ No valid clients were created.")
            return

        if not self.settings.basic_auth:
            self.logger.warning("⚠️ No authentication string provided. Client connections will be unauthenticated.")

        self.logger.info(f"✅ Connected clients: {list(clients.keys())}")

        try:
            self.proxy = await MCPProxyServer.create(clients_manager)

            await self.start_server()
        finally:
            await clients_manager.close()


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
        if self.settings.transport == "stdio":
            await self.start_stdio_server()
        elif self.settings.transport == "sse":
            await self.start_sse_server()
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
                Route(f"{url_prefix}/mcp_tools", endpoint=self.handle_mcp_tools, methods=["GET"]),
            ],
        )

        starlette_app.add_middleware(PortHeaderMiddleware, port=self.settings.port)
        config = uvicorn.Config(
            starlette_app,
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def handle_mcp_servers(self, request: Request) -> JSONResponse:
        """Handle GET/POST/DELETE to list, add, or remove MCP clients at runtime."""
        method = request.method

        if method == "GET":
            servers = list(self.proxy.client_manager.clients.keys())
            return JSONResponse({"active_servers": servers})

        elif method == "POST":
            try:
                payload = await request.json()

                if "mcpServers" not in payload:
                    return JSONResponse({"error": "Missing 'mcpServers' in payload"}, status_code=400)

                # Create clients from full `mcpServers` dict
                new_clients = await self.proxy.client_manager.create_clients(payload)

                if not new_clients:
                    return JSONResponse({"error": "No clients were created"}, status_code=500)

                for name, client in new_clients.items():
                    await self.proxy.register_client(name, client)

                return JSONResponse({"message": f"Added {list(new_clients.keys())}"})

            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        elif method == "DELETE":
            name = request.path_params.get("name")
            if not name:
                return JSONResponse({"error": "Missing client name in path"}, status_code=400)

            client = self.proxy.client_manager.clients.get(name)
            if not client:
                return JSONResponse({"error": f"No client named '{name}'"}, status_code=404)

            try:
                await self.proxy.unregister_client(name)
                return JSONResponse({"message": f"Client '{name}' removed successfully"})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        return JSONResponse({"error": f"Unsupported method: {method}"}, status_code=405)

    async def handle_mcp_tools(self, request: Request) -> JSONResponse:
        """Return the list of currently available tools grouped by server."""
        try:
            if not self.proxy:
                return JSONResponse({"error": "Proxy not initialized"}, status_code=500)

            tools_by_server = {}
            for server_name, client in self.proxy.client_manager.clients.items():
                try:
                    tools = await client.list_tools()
                    tools_by_server[server_name] = [tool.name for tool in tools.tools]
                except Exception as e:
                    tools_by_server[server_name] = f"❌ Error: {str(e)}"

            return JSONResponse({"tools": tools_by_server})

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
