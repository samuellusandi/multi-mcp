"""Prompts capability handler."""

from mcp import types
from mcp.client.session import ClientSession

from ..mcp_client import MCPClientManager
from .base import BaseCapabilityHandler


class PromptsCapabilityHandler(BaseCapabilityHandler):
    """Handles prompts capability for MCP proxy."""

    async def initialize_for_client(self, name: str, client: ClientSession) -> None:
        """Initialize prompts for a specific client."""
        try:
            prompts_result = await client.list_prompts()
            for prompt in prompts_result.prompts:
                self.mapping[prompt.name] = client
        except Exception as e:
            self.error_handler.logger.error(f"Failed to initialize prompts for {name}: {e}")

    async def list_prompts(self, client_manager: MCPClientManager) -> types.ServerResult:
        """List all available prompts."""
        all_prompts = []
        for name, client in client_manager.clients.items():
            try:
                prompts = await client.list_prompts()
                all_prompts.extend(prompts.prompts)
            except Exception as e:
                self.error_handler.logger.error(f"Error fetching prompts from {name}: {e}")

        return types.ServerResult(prompts=all_prompts)

    async def get_prompt(self, req: types.GetPromptRequest) -> types.ServerResult:
        """Get a specific prompt."""
        prompt_name = req.params.name
        client = self.mapping.get(prompt_name)

        if not client:
            return self.error_handler.log_not_found_error("Prompt", prompt_name)

        try:
            result = await client.get_prompt(req.params)
            return types.ServerResult(result)
        except Exception as e:
            return self.error_handler.log_and_return_error("get prompt", prompt_name, e)

    async def complete(self, req: types.CompleteRequest) -> types.ServerResult:
        """Complete a prompt."""
        prompt_name = req.params.prompt
        client = self.mapping.get(prompt_name)

        if not client:
            return self.error_handler.log_not_found_error("Prompt", f"{prompt_name} for completion")

        try:
            result = await client.complete(req.params)
            return types.ServerResult(result)
        except Exception as e:
            return self.error_handler.log_and_return_error("complete prompt", prompt_name, e)
