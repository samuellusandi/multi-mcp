"""MCP Proxy Server."""

from typing import Any, Optional

from mcp import server, types
from mcp.client.session import ClientSession

from src.multimcp.mcp_client import MCPClientManager
from src.utils.logger import get_logger

from .capabilities import PromptsCapabilityHandler, ResourcesCapabilityHandler, ToolsCapabilityHandler


class MCPProxyServer(server.Server):
    """An MCP Proxy Server that forwards requests to remote MCP servers."""

    def __init__(self, client_manager: MCPClientManager):
        """Initialize the MCP proxy server."""
        super().__init__("MultiMCP proxy Server")
        self.capabilities: dict[str, types.ServerCapabilities] = {}
        self.tools_handler = ToolsCapabilityHandler()
        self.prompts_handler = PromptsCapabilityHandler()
        self.resources_handler = ResourcesCapabilityHandler()
        self._register_request_handlers()
        self.logger = get_logger("multi_mcp.ProxyServer")
        self.client_manager: Optional[MCPClientManager] = client_manager

    @classmethod
    async def create(cls, client_manager: MCPClientManager) -> "MCPProxyServer":
        """Factory method to create and initialize the proxy with clients."""
        proxy = cls(client_manager)
        await proxy.initialize_remote_clients()
        return proxy

    async def initialize_remote_clients(self) -> None:
        """Initialize all remote clients and store their capabilities."""
        for name, client in self.client_manager.clients.items():
            try:
                await self.initialize_single_client(name, client)
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize client {name}: {str(e)}")

    async def initialize_single_client(self, name: str, client: ClientSession) -> None:
        """Initialize a specific client and map its capabilities."""
        self.logger.info(f"try initialize client {name}: {client}")
        result = await client.initialize()
        self.capabilities[name] = result.capabilities

        if result.capabilities.tools:
            await self.tools_handler.initialize_for_client(name, client)

        if result.capabilities.prompts:
            await self.prompts_handler.initialize_for_client(name, client)

        if result.capabilities.resources:
            await self.resources_handler.initialize_for_client(name, client)

    async def register_client(self, name: str, client: ClientSession) -> None:
        """Add a new client and register its capabilities."""
        self.client_manager.clients[name] = client
        # Re-fetch capabilities (like on startup)
        await self.initialize_single_client(name, client)

    async def unregister_client(self, name: str) -> None:
        """Remove a client and clean up all its associated mappings."""
        client = self.client_manager.clients.get(name)
        if not client:
            self.logger.warning(f"⚠️ Tried to unregister unknown client: {name}")
            return

        self.logger.info(f"🗑️ Unregistering client: {name}")
        del self.client_manager.clients[name]

        self.capabilities.pop(name, None)

        self.tools_handler.cleanup_for_client(client)
        self.prompts_handler.cleanup_for_client(client)
        self.resources_handler.cleanup_for_client(client)

        self.logger.info(f"✅ Client '{name}' fully unregistered.")


    ## Tools capabilities
    async def _list_tools(self, _: Any) -> types.ServerResult:
        """Aggregate tools from all remote MCP servers and return a combined list."""
        return await self.tools_handler.list_tools(self.client_manager)

    async def _call_tool(self, req: types.CallToolRequest) -> types.ServerResult:
        """Invoke a tool on the correct backend MCP server."""
        return await self.tools_handler.call_tool(req)

    ## Prompts capabilities
    async def _list_prompts(self, _: Any) -> types.ServerResult:
        """Aggregate prompts from all remote MCP servers and return a combined list."""
        return await self.prompts_handler.list_prompts(self.client_manager)

    async def _get_prompt(self, req: types.GetPromptRequest) -> types.ServerResult:
        """Fetch a specific prompt from the correct backend MCP server."""
        return await self.prompts_handler.get_prompt(req)

    async def _complete(self, req: types.CompleteRequest) -> types.ServerResult:
        """Execute a prompt completion on the relevant MCP server."""
        return await self.prompts_handler.complete(req)

    ## Resources capabilities
    async def _list_resources(self, _: Any) -> types.ServerResult:
        """Aggregate resources from all remote MCP servers and return a combined list."""
        return await self.resources_handler.list_resources(self.client_manager)

    async def _read_resource(self, req: types.ReadResourceRequest) -> types.ServerResult:
        """Read a resource from the appropriate backend MCP server."""
        return await self.resources_handler.read_resource(req)
    async def _subscribe_resource(self, req: types.SubscribeRequest) -> types.ServerResult:
        """Subscribe to a resource for updates on a backend MCP server."""
        return await self.resources_handler.subscribe_resource(req)

    async def _unsubscribe_resource(self, req: types.UnsubscribeRequest) -> types.ServerResult:
        """Unsubscribe from a previously subscribed resource."""
        return await self.resources_handler.unsubscribe_resource(req)

    # Utilization function
    async def _set_logging_level(self, req: types.SetLevelRequest) -> types.ServerResult:
        """Broadcast a new logging level to all connected clients."""
        for client in self.client_manager.clients.values():
            try:
                await client.set_logging_level(req.params.level)
            except Exception as e:
                self.logger.error(f"❌ Failed to set logging level on client: {e}")

        return types.ServerResult(types.EmptyResult())

    async def _send_progress_notification(self, req: types.ProgressNotification) -> None:
        """Relay a progress update to all backend clients."""
        for client in self.client_manager.clients.values():
            try:
                await client.send_progress_notification(
                    req.params.progressToken,
                    req.params.progress,
                    req.params.total,
                )
            except Exception as e:
                self.logger.error(f"❌ Failed to send progress notification: {e}")


    def _register_request_handlers(self) -> None:
        """Dynamically registers handlers for all MCP requests."""
        # Register all request handlers
        self.request_handlers[types.ListPromptsRequest] = self._list_prompts
        self.request_handlers[types.GetPromptRequest]   = self._get_prompt
        self.request_handlers[types.CompleteRequest]    = self._complete

        self.request_handlers[types.ListResourcesRequest] = self._list_resources
        self.request_handlers[types.ReadResourceRequest]  = self._read_resource
        self.request_handlers[types.SubscribeRequest]     = self._subscribe_resource
        self.request_handlers[types.UnsubscribeRequest]   = self._unsubscribe_resource


        self.request_handlers[types.ListToolsRequest] = self._list_tools
        self.request_handlers[types.CallToolRequest]  = self._call_tool

        self.notification_handlers[types.ProgressNotification] = self._send_progress_notification

        self.request_handlers[types.SetLevelRequest]           = self._set_logging_level
