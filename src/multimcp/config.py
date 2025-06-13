"""Configuration loading and validation for MultiMCP."""

import json
import os
from typing import Any, Dict

from src.utils.logger import get_logger

from .constants import DEFAULT_CONFIG_PATH, MCP_SERVERS_KEY
from .exceptions import ConfigurationError


class ConfigurationManager:
    """Handles loading and validation of MCP configuration."""

    def __init__(self):
        """Initialize the configuration manager."""
        self.logger = get_logger("multi_mcp.ConfigManager")

    def load_config(self, path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
        """Load and validate MCP configuration from file."""
        if not os.path.exists(path):
            raise ConfigurationError(f"Configuration file {path} does not exist.")

        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Error parsing JSON configuration: {e}") from e

        self._validate_config(data)
        return data

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate the loaded configuration."""
        if not isinstance(config, dict):
            raise ConfigurationError("Configuration must be a JSON object.")

        if MCP_SERVERS_KEY not in config:
            raise ConfigurationError(f"Configuration must contain '{MCP_SERVERS_KEY}' key.")

        servers = config[MCP_SERVERS_KEY]
        if not isinstance(servers, dict) or not servers:
            raise ConfigurationError(f"'{MCP_SERVERS_KEY}' must be a non-empty object.")

    def get_mcp_servers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract MCP servers configuration."""
        return config.get(MCP_SERVERS_KEY, {})
