from datetime import timedelta
from typing import List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxTaskTypes, StartContainerArgs, SandboxBaseArgs


class CodeActAgentWorkflow:

    def __init__(self):
        super().__init__()
        self.container_id: str | None = None

    async def start_sandbox_container(self,
                                      python_packages: Optional[List[str]] = None,
                                      system_packages: Optional[List[str]] = None
                                      ):
        self.container_id = await workflow.execute_activity(
            activity=SandboxTaskTypes.START_CONTAINER,
            arg=StartContainerArgs(
                python_packages=python_packages,
                system_packages=system_packages
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                maximum_interval=timedelta(seconds=10),
            ),
            summary=f"Executing task {SandboxTaskTypes.START_CONTAINER.value}"
        )

    async def stop_sandbox_container(self):
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
