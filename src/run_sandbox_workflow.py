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
        arg="Make a pandas dataframe with all the numbers from 1 to 100 and then append in a new column the pow of 2 and in another one the radical square ONLY IF INTEGER",
        id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING
    )
    print(output)


async def main():
    """Main entry point."""

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
