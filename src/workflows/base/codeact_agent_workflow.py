from typing import List, Optional

from temporalio import workflow
from temporalio.workflow import ChildWorkflowHandle


with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxTaskTypes, StartContainerArgs, SandboxBaseArgs, SandboxInputTask
    from docker_sandbox.container_sandbox import StatelessPersistentSandbox


class CodeActAgentWorkflow:

    def __init__(self):
        super().__init__()
        self.container_id: str | None = None
        self.child_workflow_id: str | None = None
        self.child_handle: ChildWorkflowHandle | None = None

    async def start_sandbox_container(self,
                                      python_packages: Optional[List[str]] = None,
                                      system_packages: Optional[List[str]] = None
                                      ):
        self.child_workflow_id = f"{workflow.info().workflow_id}-{self.container_id}"
        self.child_handle = await workflow.start_child_workflow(
            workflow='SandboxWorkflow',
            id=self.child_workflow_id,
            task_queue=workflow.info().task_queue,
        )

        self.container_id = await StatelessPersistentSandbox.trigger_and_wait_result(
            handle=self.child_handle,
            sandbox_input=SandboxInputTask(task_name=SandboxTaskTypes.START_CONTAINER,
                                           task_args=StartContainerArgs(
                                               python_packages=python_packages,
                                               system_packages=system_packages
                                           )))

    async def stop_sandbox_container(self):
        await StatelessPersistentSandbox.trigger_and_wait_result(
            handle=self.child_handle,
            sandbox_input=SandboxInputTask(task_name=SandboxTaskTypes.STOP_CONTAINER,
                                           task_args=SandboxBaseArgs(container_id=self.container_id))
        )
        self.container_id = None
