import asyncio
from typing import Dict, List, Callable, Any

import jsonref
from mcp import Tool
from pydantic_ai.mcp import MCPServerStdio

from temporal.pydanticai.codeact.datamodels.sandbox import StartContainerArgs, ExecutePythonArgs
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox


class MCPSandboxExecutor:
    """
    Execute Python code in a sandboxed environment with MCP tools available as synchronous functions.

    This class manages the event loop coordination needed to call async MCP tools
    from within synchronous exec() contexts. Supports multiple MCP servers.

    Usage:
        async with MCPServerStdio("uvx", ["mcp-server-time"]) as time_server, \\
                   MCPServerStdio("uvx", ["mcp-server-fetch"]) as fetch_server:
            executor = await MCPSandboxExecutor.create([time_server, fetch_server])
            await executor.execute('print(get_current_time(timezone="UTC"))')
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
        self._namespace: Dict[str, Any] = {'__builtins__': __builtins__}

        # Create callable wrappers for all tools from all servers
        for server, tools in tools_by_server:
            for tool in tools:
                func = self._create_tool_wrapper(server, tool)
                # Check for name conflicts
                if func.__name__ in self._namespace and func.__name__ != '__builtins__':
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

    async def execute(self, code: str, namespace: Dict[str, Any] | None = None) -> None:
        """
        Execute Python code with MCP tools available.

        Args:
            code: Python code to execute
            namespace: Optional additional namespace items (merged with tool functions)
        """
        # Merge custom namespace with tool functions
        exec_namespace = {**self._namespace}
        if namespace:
            exec_namespace.update(namespace)

        # Run exec in thread pool to keep event loop responsive
        def run_code():
            exec(code, exec_namespace)

        await asyncio.get_running_loop().run_in_executor(None, run_code)

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
        """Get the execution namespace with all tools."""
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


# async def example_basic():
#     """Example: Basic usage with time tools."""
#     code = 'print(get_current_time(timezone="America/New_York"))'
#
#     async with MCPServerStdio("uvx", ["mcp-server-time"]) as server:
#         executor = await MCPSandboxExecutor.create(server)
#
#         print(f"Available tools: {executor.available_tools}\n")
#         print(f"Executing: {code}\n")
#
#         await executor.execute(code)
#         print("\n✓ Execution completed!")
#
#
# async def example_multiple_calls():
#     """Example: Multiple tool calls in one execution."""
#     code = '''
# # Get time in different timezones
# ny_time = get_current_time(timezone="America/New_York")
# tokyo_time = get_current_time(timezone="Asia/Tokyo")
# london_time = get_current_time(timezone="Europe/London")
#
# print(f"New York: {ny_time}")
# print(f"Tokyo: {tokyo_time}")
# print(f"London: {london_time}")
# '''
#
#     async with MCPServerStdio("uvx", ["mcp-server-time"]) as server:
#         executor = await MCPSandboxExecutor.create(server)
#         await executor.execute(code)
#
#
# async def example_with_custom_namespace():
#     """Example: Execute code with custom variables in namespace."""
#     code = '''
# current = get_current_time(timezone=my_timezone)
# print(f"{city}: {current}")
# '''
#
#     async with MCPServerStdio("uvx", ["mcp-server-time"]) as server:
#         executor = await MCPSandboxExecutor.create(server)
#
#         # Add custom variables to namespace
#         custom_vars = {
#             'my_timezone': 'America/Los_Angeles',
#             'city': 'Los Angeles'
#         }
#
#         await executor.execute(code, namespace=custom_vars)
#
#
async def example_multiple_servers():
    """Example: Using tools from multiple MCP servers."""
    code = '''
# Use tools from different servers
time_data = get_current_time(timezone="UTC")
print(f"Current UTC time: {time_data}")

# Fetch a web page
try:
    webpage = fetch(url="https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md")
    print(f"\\nFetched {len(webpage)} characters from github")
    print(f"Preview: {webpage[:100]}...")
except Exception as e:
    print(f"\\nFetch failed: {e}")
'''
    print("\n1. Starting container...")
    sandbox = PersistentContainerSandbox()
    container_id = await sandbox.start_container(StartContainerArgs())
    print(f"   Container started: {container_id[:12]}")

    time_server = MCPServerStdio("uvx", ["mcp-server-time"])
    fetch_server = MCPServerStdio("uvx", ["mcp-server-fetch", "--ignore-robots-txt"])

    result = await sandbox.execute_python(
        ExecutePythonArgs(container_id=container_id, code=code),
        mcp_servers=[time_server, fetch_server]
    )

    print(f"   Success: {result['success']}")
    if result['success']:
        print(f"   Output:\n{result['output']}")
    else:
        print(f"   Error: {result['error']}")


async def main():
    # """Run all examples."""
    # print("=" * 60)
    # print("Example 1: Basic usage")
    # print("=" * 60)
    # await example_basic()
    #
    # print("\n" + "=" * 60)
    # print("Example 2: Multiple tool calls")
    # print("=" * 60)
    # await example_multiple_calls()
    #
    # print("\n" + "=" * 60)
    # print("Example 3: Custom namespace")
    # print("=" * 60)
    # await example_with_custom_namespace()
    #
    print("\n" + "=" * 60)
    print("Example 4: Multiple MCP servers")
    print("=" * 60)
    await example_multiple_servers()


if __name__ == "__main__":
    asyncio.run(main())
