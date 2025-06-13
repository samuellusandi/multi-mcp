"""MCP Client Manager."""

import os
from contextlib import AsyncExitStack
from typing import Dict, Optional

from langchain_mcp_adapters.sessions import DEFAULT_ENCODING, DEFAULT_ENCODING_ERROR_HANDLER
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client

from src.utils.logger import get_logger

from .constants import MCP_SERVERS_KEY
from .exceptions import ClientInitializationError


class MCPClientManager:
    """Manages the lifecycle of multiple MCP clients (either stdio or SSE).

    Handles creation, storage, and graceful cleanup of client sessions.
    """

    def __init__(self):
        """Initialize the MCP client manager."""
        self.stack = AsyncExitStack()
        self.clients: Dict[str, ClientSession] = {}
        self.logger = get_logger("multi_mcp.ClientManager")

    async def create_clients(self, name: str, config: dict) -> Dict[str, ClientSession]:
        """Creates MCP clients defined in the given config.

        Supports both stdio and SSE transport.

        Args:
            name (str): Name of the client.
            config (dict): Configuration dictionary that may contain "mcpServers" key.

        Returns:
            Dict[str, ClientSession]: Dictionary mapping server names to live ClientSession objects.
        """
        await self.stack.__aenter__()

        if MCP_SERVERS_KEY not in config:
            self.logger.info("⚠️ No 'mcpServers' key found in config. Will assume a single client.")
            await self._initialize_single_client(name, config)
            return self.clients

        for server_name, server_config in config.get(MCP_SERVERS_KEY, {}).items():
            if server_name in self.clients:
                self.logger.warning(f"⚠️ Client '{server_name}' already exists and will be overridden.")
            await self._initialize_single_client(server_name, server_config)

        return self.clients

    async def _initialize_single_client(self, name: str, server: dict) -> None:
        """Initialize a single client from configuration."""
        try:
            command = server.get("command")
            url = server.get("url")

            if command:
                session = await self._create_stdio_client(name, server)
            elif url:
                session = await self._create_sse_client(name, server)
            else:
                raise ClientInitializationError("Either 'command' or 'url' must be provided in the server config.")

            self.clients[name] = session
            self.logger.info(f"✅ Connected to {name}")

        except Exception as e:
            self.logger.error(f"❌ Failed to create client for {name}: {e}")

    async def _create_stdio_client(self, name: str, server: dict) -> ClientSession:
        """Create a stdio client from configuration."""
        self.logger.info(f"🔌 Creating stdio client for {name}")

        args = server.get("args", [])
        env = server.get("env", {})
        encoding = server.get("encoding", DEFAULT_ENCODING)
        encoding_error_handler = server.get("encoding_error_handler", DEFAULT_ENCODING_ERROR_HANDLER)

        merged_env = os.environ.copy()
        merged_env.update(env)

        params = StdioServerParameters(
            command=server["command"],
            args=args,
            env=merged_env,
            encoding=encoding,
            encoding_error_handler=encoding_error_handler,
        )
        read, write = await self.stack.enter_async_context(stdio_client(params))
        return await self.stack.enter_async_context(ClientSession(read, write))

    async def _create_sse_client(self, name: str, server: dict) -> ClientSession:
        """Create an SSE client from configuration."""
        self.logger.info(f"🌐 Creating SSE client for {name}")

        read, write = await self.stack.enter_async_context(sse_client(url=server["url"]))
        return await self.stack.enter_async_context(ClientSession(read, write))

    def get_client(self, name: str | None) -> Optional[ClientSession]:
        """Retrieves an existing client by name.

        Args:
            name (str | None): The name of the client (as defined in config). Provides the first item
                in the `mcpServers` dict if `name` is None.

        Returns:
            Optional[ClientSession]: The ClientSession object, or None if not found.
        """
        if name is None:
            return next(iter(self.clients.values()), None)
        return self.clients.get(name)

    async def close(self) -> None:
        """Closes all clients and releases resources managed by the async context stack."""
        await self.stack.aclose()
