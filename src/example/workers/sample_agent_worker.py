"""
Temporal worker for running sandbox and agent workflows.

This module sets up and runs a Temporal worker that can execute:
- SandboxWorkflow: Individual sandbox operations
- SimpleAgentWorkflow: Complete agent execution with sandbox

The worker registers all necessary activities and plugins for PydanticAI
agent execution within Temporal workflows.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv, find_dotenv
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

from example.agents.simple_agent import SimpleAgent
from example.workflows.simple_agent_workflow import SimpleAgentWorkflow
from temporal.pydanticai.codeact.utils.common_utils import load_config, read_prompts, get_temporal_client
from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner

load_dotenv(find_dotenv())
logging.basicConfig(level=logging.INFO)


async def run_worker():
    app_configurations = load_config()
    prompts = read_prompts()
    client = await get_temporal_client(app_configurations['temporal'],
                                       plugins=[PydanticAIPlugin()],
                                       )
    task_queue = os.getenv('TASK_QUEUE', 'sample_queue')
    gemini_configs = app_configurations['llm']['gemini']
    agent = await SimpleAgent.from_agent_confs(
        agent_builder=AgentBuilder(prompts=prompts.agent_prompts, model_configs=gemini_configs),
    )
    workflows = [SimpleAgentWorkflow]

    runner = await CodeActWorkerRunner.from_args(
        temporal_client=client,
        task_queue=task_queue,
        agents=[agent],
        workflows=workflows,
    )
    await runner.run()


if __name__ == '__main__':
    asyncio.run(run_worker())
