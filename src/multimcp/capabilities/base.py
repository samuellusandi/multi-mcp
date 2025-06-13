"""Base class for capability handlers."""

from abc import ABC, abstractmethod
from typing import Dict

from mcp.client.session import ClientSession

from ..error_handling import ErrorHandler


class BaseCapabilityHandler(ABC):
    """Base class for MCP capability handlers."""

    def __init__(self):
        """Initialize the base capability handler."""
        self.error_handler = ErrorHandler(self.__class__.__name__)
        self.mapping: Dict[str, ClientSession] = {}

    @abstractmethod
    async def initialize_for_client(self, name: str, client: ClientSession) -> None:
        """Initialize capabilities for a specific client."""
        pass

    def cleanup_for_client(self, client: ClientSession) -> None:
        """Clean up mappings for a specific client."""
        self.mapping = {k: v for k, v in self.mapping.items() if v != client}
