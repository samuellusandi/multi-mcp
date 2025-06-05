"""Tools capability handler."""

from dataclasses import dataclass
from typing import Dict, List

from mcp import types
from mcp.client.session import ClientSession

from ..mcp_client import MCPClientManager
from .base import BaseCapabilityHandler


@dataclass
class ToolMapping:
    """Mapping of tool to its server and client."""
    server_name: str
    client: ClientSession
    tool: types.Tool

class ToolsCapabilityHandler(BaseCapabilityHandler):
    """Handles tools capability for MCP proxy."""

    def __init__(self):
        """Initialize the tools capability handler."""
        super().__init__()
        self.tool_mappings: Dict[str, ToolMapping] = {}

    async def initialize_for_client(self, name: str, client: ClientSession) -> None:
        """Initialize tools for a specific client."""
        try:
            tools_result = await client.list_tools()
            for tool in tools_result.tools:
                key = self._make_key(name, tool.name)
                self.tool_mappings[key] = ToolMapping(
                    server_name=name,
                    client=client,
                    tool=tool
                )
        except Exception as e:
            self.error_handler.logger.error(f"Failed to initialize tools for {name}: {e}")

    async def list_tools(self, client_manager: MCPClientManager) -> types.ServerResult:
        """List all available tools."""
        all_tools = []
        for name, client in client_manager.clients.items():
            try:
                tools = await self._get_tools_for_client(name, client)
                all_tools.extend(tools)
            except Exception as e:
                self.error_handler.logger.error(f"Error fetching tools from {name}: {e}")

        return types.ServerResult(tools=all_tools)

    async def call_tool(self, req: types.CallToolRequest) -> types.ServerResult:
        """Call a specific tool."""
        tool_name = req.params.name
        tool_mapping = self.tool_mappings.get(tool_name)

        if not tool_mapping:
            return self.error_handler.log_not_found_error("Tool", tool_name)

        try:
            self.error_handler.logger.info(f"✅ Calling tool '{tool_name}' on its associated server")
            result = await tool_mapping.client.call_tool(
                tool_mapping.tool.name,
                req.params.arguments or {}
            )
            return types.ServerResult(result)
        except Exception as e:
            return self.error_handler.log_and_return_error("call tool", tool_name, e)

    def cleanup_for_client(self, client: ClientSession) -> None:
        """Clean up tool mappings for a specific client."""
        self.tool_mappings = {k: v for k, v in self.tool_mappings.items() if v.client != client}

    async def _get_tools_for_client(self, server_name: str, client: ClientSession) -> List[types.Tool]:
        """Get tools for a client with namespaced names."""
        tool_list = []
        tools_result = await client.list_tools()

        for tool in tools_result.tools:
            key = self._make_key(server_name, tool.name)
            namespaced_tool = tool.model_copy()
            namespaced_tool.name = key
            tool_list.append(namespaced_tool)

        return tool_list

    @staticmethod
    def _make_key(server_name: str, item_name: str) -> str:
        """Create namespaced key."""
        return f"{server_name}__{item_name}"
