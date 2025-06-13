"""HTTP route handlers for MultiMCP."""

from typing import Dict

from starlette.requests import Request
from starlette.responses import JSONResponse

from src.utils.logger import get_logger

from .mcp_client import MCPClientManager
from .mcp_proxy import MCPProxyServer


class RouteHandlers:
    """Handles HTTP routes for MultiMCP server."""

    def __init__(self, client_managers: Dict[str, MCPClientManager], proxies: Dict[str, MCPProxyServer]):
        """Initialize the RouteHandlers."""
        self.client_managers = client_managers
        self.proxies = proxies
        self.logger = get_logger("multi_mcp.RouteHandlers")

    async def handle_mcp_servers(self, request: Request) -> JSONResponse:
        """Handle GET requests to list MCP clients at runtime."""
        servers = list(self.client_managers.keys())
        return JSONResponse({"active_servers": servers})

    async def handle_mcp_tools(self, request: Request) -> JSONResponse:
        """Return the list of currently available tools grouped by server."""
        try:
            if not self.proxies:
                return JSONResponse({"error": "Proxy not initialized"}, status_code=500)

            tools_by_server = {}
            for server_name, client_manager in self.client_managers.items():
                try:
                    client = client_manager.get_client(server_name)
                    if client:
                        tools = await client.list_tools()
                        tools_by_server[server_name] = [tool.name for tool in tools.tools]
                    else:
                        tools_by_server[server_name] = "❌ Error: Client not found"
                except Exception as e:
                    tools_by_server[server_name] = f"❌ Error: {str(e)}"

            return JSONResponse({"tools": tools_by_server})

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
