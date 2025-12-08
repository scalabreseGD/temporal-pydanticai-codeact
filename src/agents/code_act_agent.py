from datetime import timedelta
from typing import List, Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxTaskTypes, StartContainerArgs


class CodeActAgent:
    def __init__(self,
                 python_packages: Optional[List[str]] = None,
                 system_packages: Optional[List[str]] = None):
        super().__init__()
        self.python_packages = python_packages
        self.system_packages = system_packages
        self.container_id: str | None = None

    async def start_container_if_workflow(self):
        if workflow.in_workflow():
            self.container_id = await workflow.execute_activity(
                activity=str(SandboxTaskTypes.START_CONTAINER.value),
                arg=StartContainerArgs(
                    python_packages=self.python_packages,
                    system_packages=self.system_packages
                ),
                start_to_close_timeout=timedelta(minutes=10),
                result_type=str
            )
        else:
            self.container_id = '_placeholder'

