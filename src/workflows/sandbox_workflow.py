from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxInputTask, SandboxTaskTypes
    import asyncio
    from collections import deque
    from datetime import timedelta


@workflow.defn
class SandboxWorkflow:

    def __init__(self):
        super().__init__()
        self.is_spawned: bool = True
        self.is_container_running: bool = False
        self.tasks: deque[SandboxInputTask] = deque()
        self.last_task_output: deque[Any] = deque()

    @workflow.run
    async def run(self):
        def contains_tasks_or_is_stopped():
            workflow.logger.info(self.tasks)
            if self.tasks or not self.is_spawned:
                return True
            return False

        while True:
            try:
                await workflow.wait_condition(contains_tasks_or_is_stopped, timeout=timedelta(minutes=30))
                if not self.is_spawned:
                    break
                task = self.tasks.popleft()
                if task.task_name != SandboxTaskTypes.START_CONTAINER and not self.is_container_running:
                    self.last_task_output.append(
                        f"Task {task.task_name} can't be run without first having the container running. "
                        f"Use {SandboxTaskTypes.START_CONTAINER.value} first")
                else:
                    task_output = await workflow.execute_activity(
                        activity=task.task_name,
                        arg=task.task_args,
                        start_to_close_timeout=timedelta(minutes=10),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            maximum_interval=timedelta(seconds=10),
                        ),
                        summary=f"Executing task {task.task_name}",
                    )
                    if task.task_name == SandboxTaskTypes.START_CONTAINER:
                        self.is_container_running = True
                    self.last_task_output.append(task_output)

            except asyncio.TimeoutError:
                self.is_spawned = False

    @workflow.signal
    async def submit_task(self, task: SandboxInputTask):
        self.tasks.append(task)

    @workflow.signal
    async def stop_workflow(self):
        self.is_spawned = False

    @workflow.query
    def task_output(self) -> Optional[Any]:
        if self.last_task_output:
            output = self.last_task_output.popleft()
            return output
        else:
            return None
