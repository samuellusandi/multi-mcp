"""MultiMCP Server."""

from typing import Any, Literal, Optional

from pydantic_settings import BaseSettings

from src.multimcp.mcp_client import MCPClientManager
from src.multimcp.mcp_proxy import MCPProxyServer
from src.utils.logger import configure_logging, get_logger

from .auth import AuthenticationManager
from .config import ConfigurationManager
from .constants import (
    DEFAULT_CONFIG_PATH,
    ERROR_EMOJI,
    MCP_SERVERS_KEY,
    ROCKET_EMOJI,
    SUCCESS_EMOJI,
    TRANSPORT_SSE,
    TRANSPORT_STDIO,
    TRANSPORT_STREAM,
)
from .route_handlers import RouteHandlers
from .transports import TRANSPORT_CLASSES


class MCPSettings(BaseSettings):
    """Configuration settings for the MultiMCP server."""
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    transport: Literal[TRANSPORT_STDIO, TRANSPORT_SSE, TRANSPORT_STREAM] = TRANSPORT_STDIO
    unify: bool = False
    sse_server_debug: bool = False
    config: str = DEFAULT_CONFIG_PATH
    basic_auth: str | None = None

class MultiMCP:
    """MultiMCP Server."""

    def __init__(self, **settings: Any):
        """Initialize the MultiMCP server."""
        self.settings = MCPSettings(**settings)
        configure_logging(level=self.settings.log_level)
        self.logger = get_logger("MultiMCP")
        self.config_manager = ConfigurationManager()
        self.auth_manager = AuthenticationManager(self.settings.basic_auth)
        self.proxies: dict[str, MCPProxyServer] = {}
        self.client_managers: dict[str, MCPClientManager] = {}
        self.route_handlers: Optional[RouteHandlers] = None


    async def run(self):
        """Entry point to run the MultiMCP server: loads config, initializes clients, starts server."""
        self.logger.info(f"{ROCKET_EMOJI} Starting MultiMCP with transport: {self.settings.transport}")

        try:
            config = self.config_manager.load_config(path=self.settings.config)
            named_config = self.config_manager.get_mcp_servers(config)

            await self._initialize_clients(named_config)
            await self._initialize_proxies()
            await self._start_server()

        except Exception as e:
            self.logger.error(f"{ERROR_EMOJI} Failed to start MultiMCP: {e}")
            return
        finally:
            await self._cleanup()

    async def _initialize_clients(self, named_config: dict) -> None:
        """Initialize all MCP clients from configuration."""
        self.client_managers = {}
        total_clients = 0

        for name, server in named_config.items():
            self.client_managers[name] = MCPClientManager()
            clients = await self.client_managers[name].create_clients(name, {MCP_SERVERS_KEY: {name: server}})

            if clients:
                total_clients += len(clients)
                self.logger.info(f"{SUCCESS_EMOJI} Connected {len(clients)} client(s) for configuration '{name}': {list(clients.keys())}")  # noqa: E501
            else:
                self.logger.warning(f"⚠️ No valid clients created for configuration '{name}'")

        if total_clients == 0:
            raise RuntimeError("No valid clients were created across all configurations.")

        self.logger.info(f"{SUCCESS_EMOJI} Total connected clients: {total_clients}")

    async def _initialize_proxies(self) -> None:
        """Initialize proxy servers for all client managers."""
        self.proxies = {}
        for name, client_manager in self.client_managers.items():
            self.proxies[name] = await MCPProxyServer.create(client_manager)

        # Initialize route handlers
        self.route_handlers = RouteHandlers(self.client_managers, self.proxies)

    async def _start_server(self) -> None:
        """Start the server using the configured transport."""
        transport_class = TRANSPORT_CLASSES.get(self.settings.transport)
        if not transport_class:
            raise ValueError(f"Unsupported transport: {self.settings.transport}")

        transport = transport_class(self.proxies, self.auth_manager, self.route_handlers)
        await transport.start_server(
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level,
            debug=self.settings.sse_server_debug
        )

    async def _cleanup(self) -> None:
        """Clean up resources."""
        for manager in self.client_managers.values():
            await manager.close()
