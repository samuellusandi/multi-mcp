"""Resources capability handler."""

from mcp import types
from mcp.client.session import ClientSession

from ..mcp_client import MCPClientManager
from .base import BaseCapabilityHandler


class ResourcesCapabilityHandler(BaseCapabilityHandler):
    """Handles resources capability for MCP proxy."""

    async def initialize_for_client(self, name: str, client: ClientSession) -> None:
        """Initialize resources for a specific client."""
        try:
            resources_result = await client.list_resources()
            for resource in resources_result.resources:
                self.mapping[resource.uri] = client
        except Exception as e:
            self.error_handler.logger.error(f"Failed to initialize resources for {name}: {e}")

    async def list_resources(self, client_manager: MCPClientManager) -> types.ServerResult:
        """List all available resources."""
        all_resources = []
        for name, client in client_manager.clients.items():
            try:
                resources = await client.list_resources()
                all_resources.extend(resources.resources)
            except Exception as e:
                self.error_handler.logger.error(f"Error fetching resources from {name}: {e}")

        return types.ServerResult(resources=all_resources)

    async def read_resource(self, req: types.ReadResourceRequest) -> types.ServerResult:
        """Read a specific resource."""
        resource_uri = req.params.uri
        client = self.mapping.get(resource_uri)

        if not client:
            return self.error_handler.log_not_found_error("Resource", resource_uri)

        try:
            result = await client.read_resource(req.params.uri)
            return types.ServerResult(result)
        except Exception as e:
            return self.error_handler.log_and_return_error("read resource", resource_uri, e)

    async def subscribe_resource(self, req: types.SubscribeRequest) -> types.ServerResult:
        """Subscribe to a resource."""
        uri = req.params.uri
        client = self.mapping.get(uri)

        if not client:
            return self.error_handler.log_not_found_error("Resource", f"{uri} for subscription")

        try:
            await client.subscribe_resource(uri)
            return types.ServerResult(types.EmptyResult())
        except Exception as e:
            return self.error_handler.log_and_return_error("subscribe to resource", uri, e)

    async def unsubscribe_resource(self, req: types.UnsubscribeRequest) -> types.ServerResult:
        """Unsubscribe from a resource."""
        uri = req.params.uri
        client = self.mapping.get(uri)

        if not client:
            return self.error_handler.log_not_found_error("Resource", f"{uri} for unsubscription")

        try:
            await client.unsubscribe_resource(uri)
            return types.ServerResult(types.EmptyResult())
        except Exception as e:
            return self.error_handler.log_and_return_error("unsubscribe from resource", uri, e)
