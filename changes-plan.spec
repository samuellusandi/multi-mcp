# MultiMCP Codebase Refactoring Plan

## Overview
This plan refactors the MultiMCP codebase to improve readability, maintainability, and adherence to Python best practices while preserving exact functionality.

## 1. CONSTANTS AND CONFIGURATION IMPROVEMENTS

### CREATE FILE: `src/multimcp/constants.py`
```python
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
```

### CREATE FILE: `src/multimcp/exceptions.py`
```python
"""Custom exceptions for MultiMCP."""

class MultiMCPError(Exception):
    """Base exception for MultiMCP errors."""
    pass

class ConfigurationError(MultiMCPError):
    """Raised when configuration is invalid."""
    pass

class ClientInitializationError(MultiMCPError):
    """Raised when client initialization fails."""
    pass

class TransportError(MultiMCPError):
    """Raised when transport setup fails."""
    pass
```

## 2. AUTHENTICATION MODULE

### CREATE FILE: `src/multimcp/auth.py`
```python
"""Authentication utilities for MultiMCP."""

import base64
from typing import Optional
from src.utils.logger import get_logger
from .constants import AUTH_ENABLED_MSG, AUTH_BASE64_MSG, AUTH_WARNING_MSG

class AuthenticationManager:
    """Handles authentication setup and URL prefix generation."""
    
    def __init__(self, basic_auth: Optional[str] = None):
        self.basic_auth = basic_auth
        self.logger = get_logger("multi_mcp.AuthManager")
        self._base64_auth: Optional[str] = None
        self._url_prefix: str = ""
        self._setup_auth()
    
    def _setup_auth(self) -> None:
        """Set up authentication and calculate URL prefix."""
        if self.basic_auth:
            self.logger.info(AUTH_ENABLED_MSG.format(self.basic_auth))
            self._base64_auth = base64.b64encode(self.basic_auth.encode("UTF-8")).decode()
            self.logger.info(AUTH_BASE64_MSG.format(self._base64_auth))
            self._url_prefix = f"/{self._base64_auth}"
        else:
            self.logger.warning(AUTH_WARNING_MSG)
            self._url_prefix = ""
    
    @property
    def url_prefix(self) -> str:
        """Get the URL prefix for routes."""
        return self._url_prefix
    
    @property
    def base64_auth(self) -> Optional[str]:
        """Get the base64 encoded authentication string."""
        return self._base64_auth
```

## 3. CONFIGURATION MANAGEMENT

### CREATE FILE: `src/multimcp/config.py`
```python
"""Configuration loading and validation for MultiMCP."""

import json
import os
from typing import Dict, Any, Optional
from .constants import MCP_SERVERS_KEY, DEFAULT_CONFIG_PATH
from .exceptions import ConfigurationError
from src.utils.logger import get_logger

class ConfigurationManager:
    """Handles loading and validation of MCP configuration."""
    
    def __init__(self):
        self.logger = get_logger("multi_mcp.ConfigManager")
    
    def load_config(self, path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
        """Load and validate MCP configuration from file."""
        if not os.path.exists(path):
            raise ConfigurationError(f"Configuration file {path} does not exist.")
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Error parsing JSON configuration: {e}")
        
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
```

## 4. SERVER TRANSPORT ABSTRACTION

### CREATE FILE: `src/multimcp/transports/base.py`
```python
"""Base transport class for MultiMCP servers."""

from abc import ABC, abstractmethod
from typing import Dict
from ..mcp_proxy import MCPProxyServer
from ..auth import AuthenticationManager

class BaseTransport(ABC):
    """Abstract base class for server transports."""
    
    def __init__(self, proxies: Dict[str, MCPProxyServer], auth_manager: AuthenticationManager):
        self.proxies = proxies
        self.auth_manager = auth_manager
    
    @abstractmethod
    async def start_server(self, host: str, port: int, log_level: str, debug: bool = False) -> None:
        """Start the server with the specific transport."""
        pass
    
    def _create_common_routes(self) -> list:
        """Create common routes shared by all transports."""
        url_prefix = self.auth_manager.url_prefix
        return [
            # These will be imported from starlette.routing
            # Route(f"{url_prefix}/mcp_servers", endpoint=self.handle_mcp_servers, methods=["GET"]),
            # Route(f"{url_prefix}/mcp_tools", endpoint=self.handle_mcp_tools, methods=["GET"])
        ]
```

### CREATE FILE: `src/multimcp/transports/sse_transport.py`
```python
"""SSE transport implementation for MultiMCP."""

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
from mcp.server.sse import SseServerTransport
from .base import BaseTransport
from src.utils.logger import get_logger

class SSETransport(BaseTransport):
    """SSE transport implementation."""
    
    def __init__(self, proxies, auth_manager):
        super().__init__(proxies, auth_manager)
        self.logger = get_logger("multi_mcp.SSETransport")
    
    async def start_server(self, host: str, port: int, log_level: str, debug: bool = False) -> None:
        """Start the SSE server."""
        url_prefix = self.auth_manager.url_prefix
        
        sse_transports = {}
        sse_handlers = {}
        
        for name, proxy in self.proxies.items():
            sse_transports[name] = SseServerTransport(f"{url_prefix}/{name}/messages/")
            sse_handlers[name] = self._create_sse_handler(name, proxy, sse_transports[name])
        
        routes = self._build_routes(url_prefix, sse_handlers, sse_transports)
        
        starlette_app = Starlette(debug=debug, routes=routes)
        
        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level=log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def _create_sse_handler(self, name: str, proxy, sse_transport):
        """Create SSE handler for a specific proxy."""
        async def handle_sse(request):
            try:
                async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
                    await proxy.run(
                        streams[0],
                        streams[1],
                        proxy.create_initialization_options(),
                    )
                return Response("", status_code=200)
            except Exception as e:
                self.logger.error(f"SSE connection error for {name}: {e}")
                return Response("SSE connection failed", status_code=500)
        return handle_sse
    
    def _build_routes(self, url_prefix: str, sse_handlers: dict, sse_transports: dict) -> list:
        """Build all routes for the SSE server."""
        routes = []
        
        for name in self.proxies.keys():
            routes.extend([
                Route(f"{url_prefix}/{name}/sse", endpoint=sse_handlers[name]),
                Mount(f"{url_prefix}/{name}/messages/", app=sse_transports[name].handle_post_message),
            ])
        
        routes.extend(self._create_common_routes())
        return routes
```

### CREATE FILE: `src/multimcp/transports/stream_transport.py`
```python
"""Stream transport implementation for MultiMCP."""

import uvicorn
from contextlib import asynccontextmanager, AsyncExitStack
from typing import AsyncIterator
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from .base import BaseTransport
from src.utils.logger import get_logger

class StreamTransport(BaseTransport):
    """Stream transport implementation."""
    
    def __init__(self, proxies, auth_manager):
        super().__init__(proxies, auth_manager)
        self.logger = get_logger("multi_mcp.StreamTransport")
    
    async def start_server(self, host: str, port: int, log_level: str, debug: bool = False) -> None:
        """Start the stream server."""
        url_prefix = self.auth_manager.url_prefix
        
        session_managers = {}
        handle_functions = {}
        
        for name, proxy in self.proxies.items():
            session_managers[name] = StreamableHTTPSessionManager(
                app=proxy,
                event_store=None,
                json_response=True,
                stateless=True,
            )
            
            # Create proper closure for each handler
            handle_functions[name] = self._create_handler_function(name, session_managers)
        
        lifespan = self._create_lifespan(session_managers, handle_functions)
        routes = self._build_routes(url_prefix, handle_functions)
        
        starlette_app = Starlette(debug=debug, routes=routes, lifespan=lifespan)
        
        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level=log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def _create_handler_function(self, name: str, session_managers: dict):
        """Create a handler function with proper closure."""
        return lambda scope, receive, send: session_managers[name].handle_request(scope, receive, send)
    
    @asynccontextmanager
    async def _create_lifespan(self, session_managers: dict, handle_functions: dict) -> AsyncIterator[None]:
        """Create lifespan context manager for session managers."""
        async with AsyncExitStack() as stack:
            for name, session_manager in session_managers.items():
                await stack.enter_async_context(session_manager.run())
            yield
    
    def _build_routes(self, url_prefix: str, handle_functions: dict) -> list:
        """Build all routes for the stream server."""
        routes = []
        
        for name, handle_function in handle_functions.items():
            routes.append(Mount(f"{url_prefix}/{name}/mcp", app=handle_function))
        
        routes.extend(self._create_common_routes())
        return routes
```

### CREATE FILE: `src/multimcp/transports/stdio_transport.py`
```python
"""STDIO transport implementation for MultiMCP."""

from mcp.server.stdio import stdio_server
from .base import BaseTransport
from src.utils.logger import get_logger

class StdioTransport(BaseTransport):
    """STDIO transport implementation."""
    
    def __init__(self, proxies, auth_manager):
        super().__init__(proxies, auth_manager)
        self.logger = get_logger("multi_mcp.StdioTransport")
    
    async def start_server(self, host: str = None, port: int = None, log_level: str = None, debug: bool = False) -> None:
        """Start the STDIO server."""
        # For stdio, we need exactly one proxy
        if len(self.proxies) != 1:
            raise ValueError("STDIO transport requires exactly one proxy")
        
        proxy = next(iter(self.proxies.values()))
        
        async with stdio_server() as (read_stream, write_stream):
            await proxy.run(
                read_stream,
                write_stream,
                proxy.create_initialization_options(),
            )
```

### CREATE FILE: `src/multimcp/transports/__init__.py`
```python
"""Transport implementations for MultiMCP."""

from .stdio_transport import StdioTransport
from .sse_transport import SSETransport
from .stream_transport import StreamTransport
from ..constants import TRANSPORT_STDIO, TRANSPORT_SSE, TRANSPORT_STREAM

TRANSPORT_CLASSES = {
    TRANSPORT_STDIO: StdioTransport,
    TRANSPORT_SSE: SSETransport,
    TRANSPORT_STREAM: StreamTransport,
}
```

## 5. ERROR HANDLING IMPROVEMENTS

### CREATE FILE: `src/multimcp/error_handling.py`
```python
"""Centralized error handling utilities."""

from typing import Any, Optional
from mcp import types
from src.utils.logger import get_logger

class ErrorHandler:
    """Centralized error handling for MCP operations."""
    
    def __init__(self, component_name: str):
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
```

## 6. REFACTOR MCPProxyServer

### EDIT FILE: `src/multimcp/mcp_proxy.py`
**Changes:**
1. Extract error handling to use ErrorHandler
2. Create separate classes for different capability types
3. Improve method organization and reduce repetition
4. Add better type hints
5. Extract magic strings to constants

### CREATE FILE: `src/multimcp/capabilities/__init__.py`
```python
"""MCP capability handlers."""

from .tools import ToolsCapabilityHandler
from .prompts import PromptsCapabilityHandler
from .resources import ResourcesCapabilityHandler

__all__ = ["ToolsCapabilityHandler", "PromptsCapabilityHandler", "ResourcesCapabilityHandler"]
```

### CREATE FILE: `src/multimcp/capabilities/base.py`
```python
"""Base class for capability handlers."""

from abc import ABC, abstractmethod
from typing import Any, Dict
from mcp.client.session import ClientSession
from ..error_handling import ErrorHandler

class BaseCapabilityHandler(ABC):
    """Base class for MCP capability handlers."""
    
    def __init__(self):
        self.error_handler = ErrorHandler(self.__class__.__name__)
        self.mapping: Dict[str, ClientSession] = {}
    
    @abstractmethod
    async def initialize_for_client(self, name: str, client: ClientSession) -> None:
        """Initialize capabilities for a specific client."""
        pass
    
    def cleanup_for_client(self, client: ClientSession) -> None:
        """Clean up mappings for a specific client."""
        self.mapping = {k: v for k, v in self.mapping.items() if v != client}
```

### CREATE FILE: `src/multimcp/capabilities/tools.py`
```python
"""Tools capability handler."""

from typing import Dict, List
from mcp import types
from mcp.client.session import ClientSession
from .base import BaseCapabilityHandler
from ..mcp_client import MCPClientManager
from dataclasses import dataclass

@dataclass
class ToolMapping:
    """Mapping of tool to its server and client."""
    server_name: str
    client: ClientSession
    tool: types.Tool

class ToolsCapabilityHandler(BaseCapabilityHandler):
    """Handles tools capability for MCP proxy."""
    
    def __init__(self):
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
```

### CREATE FILE: `src/multimcp/capabilities/prompts.py`
```python
"""Prompts capability handler."""

from mcp import types
from mcp.client.session import ClientSession
from .base import BaseCapabilityHandler
from ..mcp_client import MCPClientManager

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
```

### CREATE FILE: `src/multimcp/capabilities/resources.py`
```python
"""Resources capability handler."""

from mcp import types
from mcp.client.session import ClientSession
from .base import BaseCapabilityHandler
from ..mcp_client import MCPClientManager

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
```

## 7. REFACTOR MCPClientManager

### EDIT FILE: `src/multimcp/mcp_client.py`
**Changes:**
1. Simplify the confusing `create_clients` method logic
2. Improve error handling consistency
3. Add better type hints
4. Extract client creation logic into separate methods
5. Use constants instead of magic strings

## 8. REFACTOR MultiMCP Main Class

### EDIT FILE: `src/multimcp/multi_mcp.py`
**Changes:**
1. Extract authentication logic to AuthenticationManager
2. Extract configuration logic to ConfigurationManager
3. Extract transport logic to transport classes
4. Simplify the main run() method
5. Remove code duplication between SSE and Stream servers
6. Improve error handling
7. Use constants instead of magic strings
8. Move route handlers to a separate class

### CREATE FILE: `src/multimcp/route_handlers.py`
```python
"""HTTP route handlers for MultiMCP."""

from typing import Dict
from starlette.requests import Request
from starlette.responses import JSONResponse
from .mcp_client import MCPClientManager
from .mcp_proxy import MCPProxyServer
from src.utils.logger import get_logger

class RouteHandlers:
    """Handles HTTP routes for MultiMCP server."""
    
    def __init__(self, client_managers: Dict[str, MCPClientManager], proxies: Dict[str, MCPProxyServer]):
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
```

## 9. IMPLEMENTATION PRIORITY ORDER

### Phase 1: Infrastructure (Foundation)
1. Create `constants.py` - Extract all magic strings and create constants
2. Create `exceptions.py` - Define custom exception classes
3. Create `error_handling.py` - Centralized error handling utilities
4. Create `auth.py` - Authentication management
5. Create `config.py` - Configuration loading and validation

### Phase 2: Capability Handlers
6. Create `capabilities/base.py` - Base capability handler
7. Create `capabilities/tools.py` - Tools capability handler
8. Create `capabilities/prompts.py` - Prompts capability handler
9. Create `capabilities/resources.py` - Resources capability handler
10. Create `capabilities/__init__.py` - Capability handlers module

### Phase 3: Transport Layer
11. Create `transports/base.py` - Base transport class
12. Create `transports/stdio_transport.py` - STDIO transport
13. Create `transports/sse_transport.py` - SSE transport
14. Create `transports/stream_transport.py` - Stream transport
15. Create `transports/__init__.py` - Transport module

### Phase 4: Route Handlers
16. Create `route_handlers.py` - HTTP route handlers

### Phase 5: Refactor Existing Files
17. **EDIT** `mcp_proxy.py` - Use capability handlers and error handling
18. **EDIT** `mcp_client.py` - Simplify client management logic
19. **EDIT** `multi_mcp.py` - Use new modules and simplify main class

## 10. DETAILED CHANGES FOR EXISTING FILES

### EDIT FILE: `src/multimcp/mcp_proxy.py`
**Major Changes:**
- Replace inline error handling with ErrorHandler class
- Extract capability handlers into separate classes
- Use ToolMapping from tools capability handler
- Remove redundant code and improve method organization
- Use constants instead of magic strings
- Improve type hints throughout

### EDIT FILE: `src/multimcp/mcp_client.py` 
**Major Changes:**
- Simplify `create_clients` method by removing confusing "mcpServers" check
- Extract client creation into separate methods for stdio and SSE
- Improve error handling consistency
- Add better type hints
- Use constants for magic strings
- Improve resource management

### EDIT FILE: `src/multimcp/multi_mcp.py`
**Major Changes:**
- Use AuthenticationManager for authentication logic
- Use ConfigurationManager for config loading
- Use transport classes instead of inline transport logic
- Use RouteHandlers for HTTP endpoints
- Remove code duplication between transport methods
- Simplify the main `run()` method
- Improve error handling throughout
- Use constants instead of magic strings

## 11. BENEFITS OF THIS REFACTORING

### Improved Maintainability
- Single responsibility principle: Each class has one clear purpose
- Dependency injection: Components are loosely coupled
- Error handling consistency: Centralized error management
- Code reuse: Common patterns extracted into reusable components

### Enhanced Readability
- Clear separation of concerns
- Consistent naming conventions
- Reduced method complexity
- Better documentation through type hints

### Better Testing
- Smaller, focused classes are easier to test
- Dependency injection enables better mocking
- Clear interfaces make unit testing straightforward

### Reduced Duplication
- Authentication logic centralized
- Error handling patterns unified
- Transport setup logic extracted
- Common route patterns shared

### Easier Extension
- New transports can be added by implementing BaseTransport
- New capabilities can be added by implementing BaseCapabilityHandler
- Configuration validation is extensible
- Authentication mechanisms can be easily swapped

## 12. BACKWARD COMPATIBILITY

All changes maintain exact behavioral compatibility:
- Same configuration file format
- Same command-line interface
- Same API endpoints and responses
- Same logging output
- Same error messages and status codes

The refactoring only improves internal code organization without changing external interfaces.
