import asyncio
import os

from dotenv import load_dotenv, find_dotenv
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.worker import Worker

from activities.common import load_config, get_temporal_client
from docker_sandbox.container_sandbox import PersistentContainerSandbox
from workflows.sandbox_workflow import SandboxWorkflow

load_dotenv(find_dotenv())


async def run_worker():
    app_configurations = load_config()
    client = await get_temporal_client(app_configurations['temporal'],
                                       plugins=[PydanticAIPlugin()],
                                       )
    sandbox_activities = PersistentContainerSandbox()
    task_queue = os.getenv('TASK_QUEUE', 'airflow-spark-kb-agent-queue')
    # utils_activities = [get_prompts, get_configs]
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[SandboxWorkflow],
        activities=sandbox_activities.activities(),
        plugins=[
            # AgentPlugin(airflow_spark_agent),
        ],
    )
    await worker.run()

if __name__ == '__main__':
    asyncio.run(run_worker())