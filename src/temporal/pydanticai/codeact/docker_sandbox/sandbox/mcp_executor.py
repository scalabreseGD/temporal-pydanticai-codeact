"""
MCP Sandbox Executor for executing code with MCP tools available.

This module provides MCPSandboxExecutor, a class that enables Python code
executed via exec() to call async MCP tools as synchronous functions.
Designed to run inside Docker containers.
"""

import asyncio
from typing import Dict, List, Callable, Any

import jsonref
from mcp import Tool
from pydantic_ai.mcp import MCPServerStdio


class MCPSandboxExecutor:
    """
    Execute Python code in a sandboxed environment with MCP tools available as synchronous functions.

    This class manages the event loop coordination needed to call async MCP tools
    from within synchronous exec() contexts. Supports multiple MCP servers.

    Usage:
        async with MCPServerStdio("uvx", ["mcp-server-time"]) as time_server, \\
                   MCPServerStdio("uvx", ["mcp-server-fetch"]) as fetch_server:
            executor = await MCPSandboxExecutor.create([time_server, fetch_server])

            # Get code to inject
            code_with_tools = executor.get_code_with_mcp_tools(user_code)

            # Or get just the namespace
            namespace = executor.namespace
    """

    def __init__(
        self,
        servers: List[MCPServerStdio],
        tools_by_server: List[tuple[MCPServerStdio, List[Tool]]],
        server_loop: asyncio.AbstractEventLoop
    ):
        self.servers = servers
        self.tools_by_server = tools_by_server
        self.server_loop = server_loop
        self._namespace: Dict[str, Any] = {}

        # Create callable wrappers for all tools from all servers
        for server, tools in tools_by_server:
            for tool in tools:
                func = self._create_tool_wrapper(server, tool)
                # Check for name conflicts
                if func.__name__ in self._namespace:
                    raise ValueError(
                        f"Tool name conflict: '{func.__name__}' exists in multiple servers. "
                        f"Please use unique tool names or prefix them."
                    )
                self._namespace[func.__name__] = func

    @classmethod
    async def create(cls, servers: List[MCPServerStdio] | MCPServerStdio) -> 'MCPSandboxExecutor':
        """
        Create an executor instance with all tools from one or more MCP servers.

        Args:
            servers: Single MCP server or list of MCP servers

        Must be called from within an async context where the MCP servers are active.
        """
        # Normalize to list
        if not isinstance(servers, list):
            servers = [servers]

        # Fetch tools from all servers (use list of tuples since servers aren't hashable)
        tools_by_server = []
        for server in servers:
            tools = await server.list_tools()
            tools_by_server.append((server, tools))

        server_loop = asyncio.get_running_loop()
        return cls(servers, tools_by_server, server_loop)

    def _create_tool_wrapper(self, server: MCPServerStdio, tool: Tool) -> Callable:
        """Convert an MCP Tool to a synchronous callable function."""
        name = tool.name.replace('-', '_')
        schema = self._get_tool_schema(tool)
        properties = schema.get('properties', {})
        required_params = set(schema.get('required', []))

        def wrapper(*args, **kwargs):
            # Build arguments dict
            inputs = {}
            param_names = list(properties.keys())

            # Handle positional args
            for i, arg in enumerate(args):
                if i < len(param_names):
                    inputs[param_names[i]] = arg

            # Add keyword args
            inputs.update(kwargs)

            # Validate required params
            for param in required_params:
                if param not in inputs:
                    raise ValueError(f"Missing required parameter: {param}")

            # Submit to server's event loop and wait for result
            future = asyncio.run_coroutine_threadsafe(
                server.direct_call_tool(tool.name, args=inputs),
                self.server_loop
            )
            return str(future.result(timeout=30.0))

        wrapper.__name__ = name
        wrapper.__doc__ = self._build_docstring(tool.description, properties, required_params)
        return wrapper

    @staticmethod
    def _get_tool_schema(tool: Tool) -> dict:
        """Extract and normalize tool schema."""
        input_schema = {
            k: v
            for k, v in jsonref.replace_refs(tool.inputSchema).items()
            if k != "$defs"
        }

        for k, v in input_schema["properties"].items():
            if "description" not in v:
                input_schema["properties"][k]["description"] = "see tool description"
            if "type" not in v:
                input_schema["properties"][k]["type"] = "string"

        return input_schema

    @staticmethod
    def _build_docstring(description: str, properties: dict, required_params: set) -> str:
        """Build a docstring from description and parameter info."""
        lines = [description, ""]

        if properties:
            lines.append("Args:")
            for param_name, param_schema in properties.items():
                param_desc = param_schema.get('description', '')
                param_type = param_schema.get('type', 'Any')
                required = " (required)" if param_name in required_params else ""
                lines.append(f"    {param_name} ({param_type}){required}: {param_desc}")

        return "\n".join(lines)

    @property
    def available_tools(self) -> List[str]:
        """Get list of available tool names from all servers."""
        all_tools = []
        for server, tools in self.tools_by_server:
            all_tools.extend([tool.name for tool in tools])
        return all_tools

    @property
    def namespace(self) -> Dict[str, Any]:
        """Get the execution namespace with all MCP tools."""
        return self._namespace.copy()

    def get_tools_by_server(self) -> Dict[str, List[str]]:
        """Get tools grouped by server command."""
        result = {}
        for idx, (server, tools) in enumerate(self.tools_by_server):
            # Use the command as a readable identifier, fallback to index
            try:
                server_id = f"{server.command} {' '.join(server.args)}"
            except AttributeError:
                server_id = f"Server {idx + 1}"
            result[server_id] = [tool.name for tool in tools]
        return result