"""
Workflow for executing individual sandbox operations.

This module provides SandboxWorkflow, a lightweight workflow for dispatching
sandbox tasks to activities. Used by StatelessPersistentSandbox to execute
sandbox operations as child workflows.
"""

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxInputTask
    from datetime import timedelta


@workflow.defn
class SandboxWorkflow:
    """
    Child workflow for executing sandbox tasks.

    A minimal workflow that dispatches a single sandbox task to its
    corresponding activity. Used by StatelessPersistentSandbox to make
    sandbox operations available as agent tools via child workflow execution.

    This enables agents to perform sandbox operations without directly managing
    container state or activity execution.

    Example:
        ```python
        # Called automatically by StatelessPersistentSandbox tools
        result = await workflow.execute_child_workflow(
            'SandboxWorkflow',
            arg=SandboxInputTask(
                task_name=SandboxTaskTypes.EXECUTE_PYTHON,
                task_args=ExecutePythonArgs(
                    container_id=container_id,
                    code="print('Hello')"
                )
            )
        )
        ```
    """

    @workflow.run
    async def run(self, task: SandboxInputTask):
        """
        Execute a sandbox task as a workflow activity.

        Dispatches the specified sandbox task to its corresponding activity
        with standard timeout and retry configuration.

        Args:
            task: Complete task specification including task type and arguments.

        Returns:
            The result of the sandbox operation. Type varies by task_name:
            - start_container: str (container_id)
            - execute_python/execute_bash: Dict[str, Any] with 'success', 'output', 'error'
            - get_python_state: Dict[str, Any] of variable name to value
            - read_file: Dict[str, Any] with 'success', 'content', 'error'
            - write_file: Dict[str, Any] with 'success' boolean
            - etc.

        Raises:
            ApplicationError: If the activity fails after 3 retry attempts.

        Note:
            All tasks have a 10-minute timeout and up to 3 retry attempts
            with 10-second maximum interval between retries.
        """
        return await workflow.execute_activity(
            activity=task.task_name,
            arg=task.task_args,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                maximum_interval=timedelta(seconds=10),
            ),
            summary=f"Executing task {task.task_name}",
        )
