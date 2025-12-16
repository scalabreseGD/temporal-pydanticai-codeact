"""Test MCP integration with Docker sandbox."""

import asyncio

from pydantic_ai.mcp import MCPServerStdio

from temporal.pydanticai.codeact.datamodels.sandbox import StartContainerArgs, ExecutePythonArgs
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox


async def test_mcp_integration():
    """Test that MCP tools work inside the Docker container."""
    print("Starting MCP integration test...")

    # Create sandbox
    sandbox = PersistentContainerSandbox()

    # Start container
    print("\n1. Starting container...")
    container_id = await sandbox.start_container(StartContainerArgs())
    print(f"   Container started: {container_id[:12]}")

    # Test 1: Execute code WITH MCP tools
    print("\n2. Testing MCP tool execution...")
    mcp_server = MCPServerStdio("uvx", ["mcp-server-time"])
    code = '''
time_ny = get_current_time(timezone="America/New_York")
time_tokyo = get_current_time(timezone="Asia/Tokyo")
print(f"New York: {time_ny}")
print(f"Tokyo: {time_tokyo}")
'''

    result = await sandbox.execute_python(
        ExecutePythonArgs(container_id=container_id, code=code),
        mcp_servers=[mcp_server]
    )

    print(f"   Success: {result['success']}")
    if result['success']:
        print(f"   Output:\n{result['output']}")
    else:
        print(f"   Error: {result['error']}")

    # Test 2: Execute regular code WITHOUT MCP tools
    print("\n3. Testing regular code execution...")
    regular_code = 'x = 42\nprint(f"The answer is {x}")'
    result2 = await sandbox.execute_python(
        ExecutePythonArgs(container_id=container_id, code=regular_code)
    )

    print(f"   Success: {result2['success']}")
    if result2['success']:
        print(f"   Output: {result2['output']}")

    # Cleanup
    print("\n4. Cleaning up...")
    await sandbox.stop_container(SandboxBaseArgs(container_id=container_id))
    print("   Container stopped")

    print("\n✅ MCP integration test completed!")


if __name__ == "__main__":
    from temporal.pydanticai.codeact.datamodels.sandbox import SandboxBaseArgs

    asyncio.run(test_mcp_integration())
