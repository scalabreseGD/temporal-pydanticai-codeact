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
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin, AgentPlugin
from temporalio.worker import Worker

from activities.common import load_config, get_temporal_client, get_prompts, get_configs, read_prompts, render_jinja
from agents.simple_agent import SimpleAgent
from datamodels.agent_builder import AgentBuilder
from docker_sandbox.container_sandbox import DurablePersistentContainerSandbox
from workflows.sandbox_workflow import SandboxWorkflow
from workflows.simple_agent_workflow import SimpleAgentWorkflow

load_dotenv(find_dotenv())
logging.basicConfig(level=logging.INFO)


async def run_worker():
    """
    Initialize and run the Temporal worker for sandbox operations.

    Sets up a Temporal worker with:
    - Workflows: SandboxWorkflow, SimpleAgentWorkflow
    - Activities: All sandbox operations + utility activities (get_prompts, etc.)
    - Plugins: PydanticAIPlugin for agent execution, AgentPlugin for SimpleAgent

    Configuration is loaded from:
    - Environment variables (.env file)
    - app_conf.yml (Temporal connection, LLM configs)
    - agent_prompts.yml (Agent prompts and instructions)

    The worker connects to the task queue specified by the TASK_QUEUE
    environment variable (defaults to 'sample_queue').

    Raises:
        FileNotFoundError: If configuration files are not found.
        ConnectionError: If unable to connect to Temporal server.

    Note:
        This function runs indefinitely until interrupted (Ctrl+C).
        The worker will process workflows and activities as they are scheduled.

    Example:
        ```bash
        # Set up environment
        export TASK_QUEUE=my-queue
        export GEMINI_API_KEY=your-key

        # Run worker
        python -m workers.sandbox_worker
        ```
    """
    app_configurations = load_config()
    prompts = read_prompts()
    client = await get_temporal_client(app_configurations['temporal'],
                                       plugins=[PydanticAIPlugin()],
                                       )
    sandbox_activities = DurablePersistentContainerSandbox()
    task_queue = os.getenv('TASK_QUEUE', 'sample_queue')
    utils_activities = [get_prompts, get_configs, render_jinja]

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
