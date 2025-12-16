#!/usr/bin/env python3
"""
Entry point for executing Python code with MCP tools available.

This script:
1. Reads MCP server configurations from environment variables
2. Starts the MCP servers
3. Creates MCPSandboxExecutor with the servers
4. Executes the user's code with MCP tools in namespace
5. Cleans up servers

Usage:
    The container should set these environment variables:
    - USER_CODE_PATH: Path to file containing user's Python code
    - MCP_SERVERS_JSON: JSON array of MCP server configurations

    Each MCP server config is: {"type": "stdio", "command": "uvx", "args": ["mcp-server-time"]}
"""

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack

# Add sandbox to path
sys.path.insert(0, "/app/sandbox")

from pydantic_ai.mcp import MCPServerStdio, MCPServerSSE, MCPServerStreamableHTTP
from mcp_executor import MCPSandboxExecutor


async def main():
    """Execute user code with MCP tools available."""

    # Read configuration from environment
    user_code_path = os.environ.get('USER_CODE_PATH')
    mcp_servers_json = os.environ.get('MCP_SERVERS_JSON', '[]')

    if not user_code_path:
        print("ERROR: USER_CODE_PATH environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Read user code
    try:
        with open(user_code_path, 'r') as f:
            user_code = f.read()
    except FileNotFoundError:
        print(f"ERROR: User code file not found: {user_code_path}", file=sys.stderr)
        sys.exit(1)

    # Parse MCP server configurations
    try:
        mcp_configs = json.loads(mcp_servers_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid MCP_SERVERS_JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # If no MCP servers, just execute the code directly
    if not mcp_configs:
        exec(user_code, {'__builtins__': __builtins__})
        return

    # Initialize MCP servers
    servers = []
    for config in mcp_configs:
        server_type = config.pop('type', 'stdio')
        if server_type == 'stdio':
            servers.append(MCPServerStdio(**config))
        elif server_type == 'sse':
            servers.append(MCPServerSSE(**config))
        elif server_type == 'streamablehttp':
            servers.append(MCPServerStreamableHTTP(**config))
        else:
            print(f"WARNING: Unsupported MCP server type: {server_type}", file=sys.stderr)

    if not servers:
        print("ERROR: No valid MCP servers configured", file=sys.stderr)
        sys.exit(1)

    # Start servers and create executor using AsyncExitStack for proper cleanup
    async with AsyncExitStack() as stack:
        # Enter all server contexts
        entered_servers = []
        for server in servers:
            entered_server = await stack.enter_async_context(server)
            entered_servers.append(entered_server)

        # Create executor with all servers
        executor = await MCPSandboxExecutor.create(entered_servers)

        # Get MCP tool namespace
        mcp_namespace = executor.namespace
        mcp_namespace['__builtins__'] = __builtins__

        # Execute user code in thread pool to keep loop responsive
        def run_user_code():
            exec(user_code, mcp_namespace)

        await asyncio.get_running_loop().run_in_executor(None, run_user_code)


if __name__ == "__main__":
    asyncio.run(main())
