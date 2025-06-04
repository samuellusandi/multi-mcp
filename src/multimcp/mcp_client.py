from contextlib import AsyncExitStack
from typing import Dict, Optional
import os

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from langchain_mcp_adapters.sessions import DEFAULT_ENCODING, DEFAULT_ENCODING_ERROR_HANDLER
from src.utils.logger import get_logger


class MCPClientManager:
    """
    Manages the lifecycle of multiple MCP clients (either stdio or SSE).
    Handles creation, storage, and graceful cleanup of client sessions.
    """

    def __init__(self):
        self.stack = AsyncExitStack()
        self.clients: Dict[str, ClientSession] = {}
        self.logger = get_logger("multi_mcp.ClientManager")

    async def create_clients(self, name: str, config: dict) -> Dict[str, ClientSession]:
        """
        Creates MCP clients defined in the given config.
        Supports both stdio and SSE transport.

        Args:
            name (str): Name of the client.
            config (dict): Configuration dictionary without the "mcpServers" key. It should already be
                extracted from the main configuration.

        Returns:
            Dict[str, ClientSession]: Dictionary mapping server names to live ClientSession objects.
        """
        await self.stack.__aenter__()

        if "mcpServers" not in config:
            self.logger.info("⚠️ No 'mcpServers' key found in config. Will assume a single client.")
            await self.initialize_single_client(name, config)
            return self.clients

        for name, server in config.get("mcpServers", {}).items():
            if name in self.clients:
                self.logger.warning(f"⚠️ Client '{name}' already exists and will be overridden.")
            await self.initialize_single_client(name, server)

        return self.clients

    async def initialize_single_client(self, name: str, server: dict) -> None:
        try:
            command = server.get("command")
            url = server.get("url")
            args = server.get("args", [])
            env = server.get("env", {})
            encoding = server.get("encoding", DEFAULT_ENCODING)
            encoding_error_handler = server.get("encoding_error_handler", DEFAULT_ENCODING_ERROR_HANDLER)

            merged_env = os.environ.copy()
            merged_env.update(env)

            if command:
                self.logger.info(f"🔌 Creating stdio client for {name}")
                params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=merged_env,
                    encoding=encoding,
                    encoding_error_handler=encoding_error_handler,
                )
                read, write = await self.stack.enter_async_context(stdio_client(params))
                session = await self.stack.enter_async_context(ClientSession(read, write))
            elif url:
                self.logger.info(f"🌐 Creating SSE client for {name}")
                read, write = await self.stack.enter_async_context(sse_client(url=url))
                session = await self.stack.enter_async_context(ClientSession(read, write))
            else:
                raise ValueError("Either 'command' or 'url' must be provided in the server config.")

            self.clients[name] = session
            self.logger.info(f"✅ Connected to {name}")

        except Exception as e:
            self.logger.error(f"❌ Failed to create client for {name}: {e}")

    def get_client(self, name: str | None) -> Optional[ClientSession]:
        """
        Retrieves an existing client by name.

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
        """
        Closes all clients and releases resources managed by the async context stack.
        """
        await self.stack.aclose()
