"""Constants used throughout the MultiMCP application."""

# Configuration keys
MCP_SERVERS_KEY = "mcpServers"

# Transport types
TRANSPORT_STDIO = "stdio"
TRANSPORT_SSE = "sse"
TRANSPORT_STREAM = "stream"

# Default configuration
DEFAULT_CONFIG_PATH = "./mcp.json"

# Authentication messages
AUTH_ENABLED_MSG = "🔑 Enabling authentication with basic auth string: {}"
AUTH_BASE64_MSG = "🔑 Enabling authentication with base64 auth string: {}"
AUTH_WARNING_MSG = "⚠️ No authentication string provided. Client connections will be unauthenticated."

# Success/error emojis and messages
SUCCESS_EMOJI = "✅"
ERROR_EMOJI = "❌"
WARNING_EMOJI = "⚠️"
ROCKET_EMOJI = "🚀"
PLUGIN_EMOJI = "🔌"
WEB_EMOJI = "🌐"
TRASH_EMOJI = "🗑️"
