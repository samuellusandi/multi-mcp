"""Base transport class for MultiMCP servers."""

from abc import ABC, abstractmethod
from typing import Dict

from ..auth import AuthenticationManager
from ..mcp_proxy import MCPProxyServer


class BaseTransport(ABC):
    """Abstract base class for server transports."""

    def __init__(self, proxies: Dict[str, MCPProxyServer], auth_manager: AuthenticationManager, route_handlers=None):
        """Initialize the BaseTransport."""
        self.proxies = proxies
        self.auth_manager = auth_manager
        self.route_handlers = route_handlers

    @abstractmethod
    async def start_server(self, host: str, port: int, log_level: str, debug: bool = False) -> None:
        """Start the server with the specific transport."""
        pass
