"""Centralized error handling utilities."""

from typing import Optional

from mcp import types

from src.utils.logger import get_logger


class ErrorHandler:
    """Centralized error handling for MCP operations."""

    def __init__(self, component_name: str):
        """Initialize the error handler."""
        self.logger = get_logger(f"multi_mcp.{component_name}")

    def create_error_result(self, message: str, error: Optional[Exception] = None) -> types.ServerResult:
        """Create a standardized error result."""
        if error:
            self.logger.error(f"❌ {message}: {error}")
        else:
            self.logger.error(f"❌ {message}")

        return types.ServerResult(
            content=[types.TextContent(type="text", text=message)],
            isError=True,
        )

    def log_and_return_error(self, operation: str, item_name: str, error: Exception) -> types.ServerResult:
        """Log an error and return a standardized error result."""
        message = f"Failed to {operation} '{item_name}'"
        return self.create_error_result(message, error)

    def log_not_found_error(self, item_type: str, item_name: str) -> types.ServerResult:
        """Log a not found error and return a standardized error result."""
        message = f"{item_type} '{item_name}' not found!"
        self.logger.error(f"⚠️ {item_type} '{item_name}' not found in any server.")
        return self.create_error_result(message)
