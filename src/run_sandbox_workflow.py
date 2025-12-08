"""
Sandbox Workflow Runner

This script demonstrates the SandboxWorkflow by:
1. Starting a Docker container
2. Executing Python code that sets variables in shared state
3. Executing more Python code that uses those variables from shared state
4. Querying the state to verify shared data
5. Cleaning up the container

Example of stateful code execution with persistence across multiple Python invocations.
"""

import asyncio
import os
from typing import Any, Optional

from dotenv import load_dotenv, find_dotenv
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import WorkflowHandle
from temporalio.common import WorkflowIDConflictPolicy

from activities.common import load_config, get_temporal_client
from datamodels.sandbox import (
    SandboxInputTask,
    SandboxTaskTypes,
    StartContainerArgs,
    ExecutePythonArgs,
    SandboxBaseArgs, ReadVariableInStateArgs,
)

load_dotenv(find_dotenv())


async def wait_for_result(handle: WorkflowHandle):
    res = None
    while res is None:
        res = await handle.query('task_output', result_type=Optional[Any])
        if res is not None:
            break
        else:
            await asyncio.sleep(5)
    return res


async def run_workflow_demo():
    """
    Run a demonstration of the SandboxWorkflow with shared state.

    This demonstrates:
    - Starting a container
    - Setting variables in first Python execution
    - Accessing those variables in second Python execution (shared state)
    - Querying the final state
    """

    # Initialize Temporal client
    app_configurations = load_config()
    client = await get_temporal_client(
        app_configurations['temporal'],
        plugins=[PydanticAIPlugin()],
    )

    # Generate unique workflow ID
    workflow_id = f"sandbox-demo-1"
    task_queue = os.getenv('TASK_QUEUE', 'sample_queue')

    output = await client.execute_workflow(
        'SimpleAgentWorkflow',
        id=workflow_id,
        task_queue=task_queue,
        arg="Generate a random pandas dataframe with 3 columns and 10 rows and return it as output",
        id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING
    )
    print(output)

    print(f"Starting workflow: {workflow_id}")
    print(f"Task queue: {task_queue}\n")

    # Start the workflow
    handle: WorkflowHandle = await client.start_workflow(
        'SandboxWorkflow',
        id=workflow_id,
        task_queue=task_queue,
        id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING
    )

    print("✓ Workflow started\n")

    # Generate container ID (in practice, this would come from the START_CONTAINER response)
    container_id_placeholder = "CONTAINER_ID_PLACEHOLDER"

    # Task 1: Start the container
    print("📦 Task 1: Starting container...")
    await handle.signal(
        'submit_task',
        SandboxInputTask(
            task_name=SandboxTaskTypes.START_CONTAINER,
            task_args=StartContainerArgs(
                python_packages=["numpy", "pandas"],
                system_packages=None,
            ),
        ),
    )
    result = await wait_for_result(handle)

    container_id = result if result else "unknown"
    print(f"✓ Container started: {container_id}\n")

    # Task 2: Execute first Python script - Set variables in shared state
    print("🐍 Task 2: Executing first Python script (setting variables)...")
    first_script = """
# First script: Initialize variables and perform calculations
import datetime

# Set some variables that will persist in state
user_name = "Alice"
calculation_result = 42 * 2
items = ["apple", "banana", "cherry"]
metadata = {
    "version": "1.0",
    "timestamp": str(datetime.datetime.now()),
    "status": "initialized"
}

print(f"First script executed!")
print(f"Set user_name: {user_name}")
print(f"Set calculation_result: {calculation_result}")
print(f"Set items: {items}")
print(f"Set metadata: {metadata}")
"""

    await handle.signal(
        'submit_task',
        SandboxInputTask(
            task_name=SandboxTaskTypes.EXECUTE_PYTHON,
            task_args=ExecutePythonArgs(
                container_id=container_id,
                code=first_script,
                persist_state=True,
            ),
        ),
    )

    result = await wait_for_result(handle)
    print(f"Output: {result}\n")

    # Task 3: Execute second Python script - Use variables from shared state
    print("🐍 Task 3: Executing second Python script (using shared state)...")
    second_script = """
# Second script: Access variables from first script's state
# These variables were set in the first script and persisted

print(f"\\nSecond script accessing shared state:")
print(f"user_name from state: {user_name}")
print(f"calculation_result from state: {calculation_result}")
print(f"items from state: {items}")
print(f"metadata from state: {metadata}")

# Perform new calculations using the persisted state
doubled = calculation_result * 2
items.append("date")  # Modify the list

# Create new variables
greeting = f"Hello, {user_name}!"
final_result = calculation_result + len(items)

print(f"\\nNew calculations:")
print(f"greeting: {greeting}")
print(f"doubled: {doubled}")
print(f"final_result: {final_result}")
print(f"modified items: {items}")
"""

    await handle.signal(
        'submit_task',
        SandboxInputTask(
            task_name=SandboxTaskTypes.EXECUTE_PYTHON,
            task_args=ExecutePythonArgs(
                container_id=container_id,
                code=second_script,
                persist_state=True,
            ),
        ),
    )

    result = await wait_for_result(handle)
    print(f"Output: {result}\n")

    # Task 4: List all variables in state
    print("📋 Task 4: Listing all variables in shared state...")
    await handle.signal(
        'submit_task',
        SandboxInputTask(
            task_name=SandboxTaskTypes.LIST_STATE_VARIABLES,
            task_args=SandboxBaseArgs(container_id=container_id),
        ),
    )

    result = await wait_for_result(handle)
    print(f"State variables: {result}\n")

    # Task 5: Read specific variable from state
    print("🔍 Task 5: Reading specific variable 'greeting' from state...")
    await handle.signal(
        'submit_task',
        SandboxInputTask(
            task_name=SandboxTaskTypes.READ_STATE_VARIABLE,
            task_args=ReadVariableInStateArgs(container_id=container_id, variable_name="greeting"),
        ),
    )

    result = await wait_for_result(handle)
    print(f"Variable 'greeting': {result}\n")

    # Task 6: Get full Python state
    print("📊 Task 6: Getting full Python state...")
    await handle.signal(
        'submit_task',
        SandboxInputTask(
            task_name=SandboxTaskTypes.GET_PYTHON_STATE,
            task_args=SandboxBaseArgs(container_id=container_id),
        ),
    )
    result = await wait_for_result(handle)
    print(f"Full state: {result}\n")

    # Task 7: Stop the container and cleanup
    print("🛑 Task 7: Stopping container and cleaning up...")
    await handle.signal(
        'submit_task',
        SandboxInputTask(
            task_name=SandboxTaskTypes.STOP_CONTAINER,
            task_args=SandboxBaseArgs(container_id=container_id),
        ),
    )
    result = await wait_for_result(handle)
    print(f"✓ Container stopped\n")

    # Stop the workflow
    print("⏹️  Stopping workflow...")
    await handle.signal('stop_workflow')

    # Wait for workflow to complete
    await handle.result()
    print("✓ Workflow completed successfully!")


async def main():
    """Main entry point."""
    print("=" * 70)
    print("Sandbox Workflow Demo - Shared State Between Python Scripts")
    print("=" * 70)
    print()

    try:
        await run_workflow_demo()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 70)
    print("Demo completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
