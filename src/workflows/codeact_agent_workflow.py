from datetime import timedelta
from typing import List, Optional, Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxTaskTypes, StartContainerArgs


class CodeActAgentWorkflow:

    def __init__(self):
        super().__init__()
        self.container_id: str | None = None

    async def start_sandbox_container(self,
                                      python_packages: Optional[List[str]] = None,
                                      system_packages: Optional[List[str]] = None
                                      ):
        self.container_id = await workflow.execute_activity(
            activity=str(SandboxTaskTypes.START_CONTAINER.value),
            arg=StartContainerArgs(
                python_packages=python_packages,
                system_packages=system_packages
            ),
            start_to_close_timeout=timedelta(minutes=10),
            result_type=str
        )

    async def stop_sandbox_container(self):
        await workflow.execute_activity(
            activity=str(SandboxTaskTypes.STOP_CONTAINER.value),
            start_to_close_timeout=timedelta(minutes=10),
            result_type=dict[str, Any]
        )
        self.container_id = None
