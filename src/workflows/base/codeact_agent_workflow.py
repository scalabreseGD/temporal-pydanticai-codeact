"""
Base workflow mixin for code-executing agents with sandbox management.

This module provides CodeActAgentWorkflow, a mixin class that adds sandbox
container lifecycle management to Temporal workflows. Workflows that include
code execution capabilities should inherit from this class.
"""

from datetime import timedelta
from typing import List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxTaskTypes, StartContainerArgs, SandboxBaseArgs


class CodeActAgentWorkflow:
    """
    Mixin for managing sandbox container lifecycle in workflows.

    Provides methods for starting and stopping Docker sandbox containers
    as part of a workflow. Workflows that execute code should inherit from
    or compose with this class to manage container lifecycle.

    The container_id is stored as workflow state and made available to
    agents via CodeActAgentDeps.

    Attributes:
        container_id: ID of the currently running sandbox container.
            None if no container is active.

    Example:
        ```python
        @workflow.defn
        class MyCodeWorkflow(CodeActAgentWorkflow):
            @workflow.run
            async def run(self, task: str) -> str:
                # Start container with packages
                await self.start_sandbox_container(
                    python_packages=['numpy', 'pandas']
                )

                try:
                    # Use self.container_id in agent deps
                    result = await agent.run(
                        user_prompt=task,
                        deps=CodeActAgentDeps(container_id=self.container_id)
                    )
                    return result.output
                finally:
                    # Always cleanup
                    await self.stop_sandbox_container()
        ```
    """

    def __init__(self):
        super().__init__()
        self.container_id: str | None = None

    async def start_sandbox_container(self,
                                      python_packages: Optional[List[str]] = None,
                                      system_packages: Optional[List[str]] = None
                                      ):
        """
        Start a new sandbox container with specified packages.

        Executes the START_CONTAINER activity to create and initialize a new
        Docker container. Installs requested packages and initializes persistent
        state. Sets self.container_id to the new container's ID.

        The container is named using the workflow ID for easy tracking and
        management across workflow executions.

        Args:
            python_packages: Optional list of Python packages to install via uv.
            system_packages: Optional list of system packages to install via apt-get.

        Returns:
            None. Sets self.container_id as a side effect.

        Raises:
            ApplicationError: If container creation or package installation fails
                after 3 retry attempts.

        Note:
            Container creation has a 10-minute timeout with up to 3 retries.
            Package installation is part of container startup.
        """
        self.container_id = await workflow.execute_activity(
            activity=SandboxTaskTypes.START_CONTAINER,
            arg=StartContainerArgs(
                python_packages=python_packages,
                system_packages=system_packages,
                container_name=workflow.info().workflow_id
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                maximum_interval=timedelta(seconds=10),
            ),
            summary=f"Executing task {SandboxTaskTypes.START_CONTAINER.value}"
        )

    async def stop_sandbox_container(self):
        """
        Stop and remove the current sandbox container.

        Executes the STOP_CONTAINER activity to stop and remove the container
        managed by this workflow. Clears self.container_id after successful stop.

        Returns:
            None. Clears self.container_id as a side effect.

        Raises:
            ValueError: If no container is currently running (container_id is None).
            ApplicationError: If container stop/removal fails after 3 retry attempts.

        Note:
            This should be called in a finally block to ensure cleanup even if
            the workflow fails. Has a 10-minute timeout with up to 3 retries.
        """
        await workflow.execute_activity(
            activity=SandboxTaskTypes.STOP_CONTAINER,
            arg=SandboxBaseArgs(container_id=self.container_id),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                maximum_interval=timedelta(seconds=10),
            ),
            summary=f"Executing {SandboxTaskTypes.STOP_CONTAINER.value} with {self.container_id}"
        )
        self.container_id = None
