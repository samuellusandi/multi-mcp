"""SSE transport implementation for MultiMCP."""

import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount, Route

from src.utils.logger import get_logger

from .base import BaseTransport


class SSETransport(BaseTransport):
    """SSE transport implementation."""

    def __init__(self, proxies, auth_manager, route_handlers=None):
        """Initialize the SSETransport."""
        super().__init__(proxies, auth_manager, route_handlers)
        self.logger = get_logger("multi_mcp.SSETransport")

    async def start_server(self, host: str, port: int, log_level: str, debug: bool = False) -> None:
        """Start the SSE server."""
        url_prefix = self.auth_manager.url_prefix

        sse_transports = {}
        sse_handlers = {}

        for name, proxy in self.proxies.items():
            sse_transports[name] = SseServerTransport(f"{url_prefix}/{name}/messages/")
            sse_handlers[name] = self._create_sse_handler(name, proxy, sse_transports[name])

        routes = self._build_routes(url_prefix, sse_handlers, sse_transports)

        # Add common routes if route handlers are available
        if self.route_handlers:
            from starlette.routing import Route
            routes.extend([
                Route(f"{url_prefix}/mcp_servers", endpoint=self.route_handlers.handle_mcp_servers, methods=["GET"]),
                Route(f"{url_prefix}/mcp_tools", endpoint=self.route_handlers.handle_mcp_tools, methods=["GET"])
            ])

        starlette_app = Starlette(debug=debug, routes=routes)

        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level=log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    def _create_sse_handler(self, name: str, proxy, sse_transport):
        """Create SSE handler for a specific proxy."""
        async def handle_sse(request):
            try:
                async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
                    await proxy.run(
                        streams[0],
                        streams[1],
                        proxy.create_initialization_options(),
                    )
                return Response("", status_code=200)
            except Exception as e:
                self.logger.error(f"SSE connection error for {name}: {e}")
                return Response("SSE connection failed", status_code=500)
        return handle_sse

    def _build_routes(self, url_prefix: str, sse_handlers: dict, sse_transports: dict) -> list:
        """Build all routes for the SSE server."""
        routes = []

        for name in self.proxies.keys():
            routes.extend([
                Route(f"{url_prefix}/{name}/sse", endpoint=sse_handlers[name]),
                Mount(f"{url_prefix}/{name}/messages/", app=sse_transports[name].handle_post_message),
            ])

        return routes
