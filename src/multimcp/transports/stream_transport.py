"""Stream transport implementation for MultiMCP."""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

import uvicorn
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

from src.utils.logger import get_logger

from .base import BaseTransport


class StreamTransport(BaseTransport):
    """Stream transport implementation."""

    def __init__(self, proxies, auth_manager, route_handlers=None):
        """Initialize the StreamTransport."""
        super().__init__(proxies, auth_manager, route_handlers)
        self.logger = get_logger("multi_mcp.StreamTransport")

    async def start_server(
        self,
        host: str,
        port: int,
        log_level: str,
        debug: bool = False,
    ) -> None:
        """Start the stream server."""
        url_prefix = self.auth_manager.url_prefix

        session_managers = {}
        handle_functions = {}

        for name, proxy in self.proxies.items():
            session_managers[name] = StreamableHTTPSessionManager(
                app=proxy,
                event_store=None,
                json_response=True,
                stateless=True,
            )

            handle_functions[name] = \
                lambda scope, receive, send, captured_name=name: (session_managers[captured_name]
                                                                  .handle_request(scope, receive, send))

        lifespan = self._create_lifespan(session_managers)
        routes = self._build_routes(url_prefix, handle_functions)

        # Add common routes if route handlers are available
        if self.route_handlers:
            from starlette.routing import Route
            routes.extend([
                Route(f"{url_prefix}/mcp_servers", endpoint=self.route_handlers.handle_mcp_servers, methods=["GET"]),
                Route(f"{url_prefix}/mcp_tools", endpoint=self.route_handlers.handle_mcp_tools, methods=["GET"])
            ])

        starlette_app = Starlette(debug=debug, routes=routes, lifespan=lifespan)

        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level=log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    def _create_handler_function(self, name: str, session_managers: dict):
        """Create a handler function with proper closure."""
        return lambda scope, receive, send: session_managers[name].handle_request(scope, receive, send)

    def _create_lifespan(self, session_managers: dict):
        """Create lifespan context manager for session managers."""
        @asynccontextmanager
        async def lifespan(app):
            async with AsyncExitStack() as stack:
                for name, session_manager in session_managers.items():
                    await stack.enter_async_context(session_manager.run())
                yield
        return lifespan

    def _build_routes(self, url_prefix: str, handle_functions: dict) -> list:
        """Build all routes for the stream server."""
        routes = []

        for name, handle_function in handle_functions.items():
            routes.append(Mount(f"{url_prefix}/{name}/mcp", app=handle_function))

        return routes
