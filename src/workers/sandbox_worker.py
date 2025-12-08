import asyncio
import os

from dotenv import load_dotenv, find_dotenv
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin, AgentPlugin
from temporalio.worker import Worker

from activities.common import load_config, get_temporal_client, get_prompts, get_configs, read_prompts
from agents.simple_agent import SimpleAgent
from datamodels.agent_builder import AgentBuilder
from docker_sandbox.container_sandbox import PersistentContainerSandbox
from workflows.sandbox_workflow import SandboxWorkflow
from workflows.simple_agent_workflow import SimpleAgentWorkflow

load_dotenv(find_dotenv())


async def run_worker():
    app_configurations = load_config()
    prompts = read_prompts()
    client = await get_temporal_client(app_configurations['temporal'],
                                       plugins=[PydanticAIPlugin()],
                                       )
    sandbox_activities = PersistentContainerSandbox()
    task_queue = os.getenv('TASK_QUEUE', 'sample_queue')
    utils_activities = [get_prompts, get_configs]

    gemini_configs = app_configurations['llm']['gemini']
    agent = await SimpleAgent.from_agent_confs(
        agent_builder=AgentBuilder(prompts=prompts.agent_prompts, model_configs=gemini_configs),
    )
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[SandboxWorkflow, SimpleAgentWorkflow],
        activities=sandbox_activities.activities() + utils_activities,
        plugins=[
            AgentPlugin(agent=agent),
        ],
    )
    await worker.run()


if __name__ == '__main__':
    asyncio.run(run_worker())
