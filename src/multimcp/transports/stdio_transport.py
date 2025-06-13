"""STDIO transport implementation for MultiMCP."""

from mcp.server.stdio import stdio_server

from src.utils.logger import get_logger

from .base import BaseTransport


class StdioTransport(BaseTransport):
    """STDIO transport implementation."""

    def __init__(self, proxies, auth_manager, route_handlers=None):
        """Initialize the STDIOTransport."""
        super().__init__(proxies, auth_manager, route_handlers)
        self.logger = get_logger("multi_mcp.StdioTransport")

    async def start_server(
        self,
        host: str = None,
        port: int = None,
        log_level: str = None,
        debug: bool = False,
    ) -> None:
        """Start the STDIO server."""
        # For stdio, we need exactly one proxy
        if len(self.proxies) != 1:
            raise ValueError("STDIO transport requires exactly one proxy")

        proxy = next(iter(self.proxies.values()))

        async with stdio_server() as (read_stream, write_stream):
            await proxy.run(
                read_stream,
                write_stream,
                proxy.create_initialization_options(),
            )
