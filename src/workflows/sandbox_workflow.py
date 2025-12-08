from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxInputTask
    from datetime import timedelta


@workflow.defn
class SandboxWorkflow:

    @workflow.run
    async def run(self, task: SandboxInputTask):
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
