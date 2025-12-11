"""
Temporal worker builder for running sandbox and agent workflows.

This module provides the `CodeActWorkerRunner` class, a flexible builder for
creating Temporal workers that can execute code-acting agents with custom
workflows and activities.

The worker automatically includes:
- SandboxWorkflow: Individual sandbox operations
- DurablePersistentContainerSandbox activities: All sandbox operations
- Utility activities: get_prompts, get_configs, render_jinja
- AgentPlugin for each provided agent

Features:
- Multi-agent support: Register multiple agents in a single worker
- Extensible workflows: Add custom workflow classes alongside defaults
- Custom activities: Inject additional activity functions as needed
- Automatic plugin registration: Each agent gets its own AgentPlugin

Example:
    ```python
    from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner
    from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent

    # Build agents
    agent = await SimpleAgent.from_agent_confs(agent_builder)

    # Create worker
    worker = await CodeActWorkerRunner.from_args(
        temporal_client=client,
        task_queue='my-queue',
        agents=[agent],
        workflows=[MyCustomWorkflow],
        activities=[my_custom_activity]
    )

    # Run worker
    await worker.run()
    ```
"""

import logging
from typing import Callable, Awaitable

from dotenv import load_dotenv, find_dotenv
from pydantic_ai.durable_exec.temporal import AgentPlugin, TemporalAgent
from temporalio.client import Client
from temporalio.worker import Worker

from temporal.pydanticai.codeact.activities.common import get_prompts, get_configs, \
    render_jinja
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import DurablePersistentContainerSandbox
from temporal.pydanticai.codeact.workflows.sandbox_workflow import SandboxWorkflow

load_dotenv(find_dotenv())
logging.basicConfig(level=logging.INFO)

ActivityFn = Callable[..., Awaitable]


class CodeActWorkerRunner:
    """
    Flexible Temporal worker builder for code-acting agents.

    This class simplifies the creation of Temporal workers that run PydanticAI
    agents with code execution capabilities. It automatically wires up:
    - Sandbox workflows and activities for Docker container management
    - Utility activities for configuration and prompt management
    - Agent plugins for durable agent execution

    Attributes:
        worker (Worker): The underlying Temporal worker instance.

    Example:
        ```python
        # Create temporal client
        client = await get_temporal_client(config['temporal'])

        # Build your agents
        agent1 = await SimpleAgent.from_agent_confs(builder1)
        agent2 = await MyCustomAgent.from_agent_confs(builder2)

        # Create worker with multiple agents and workflows
        worker = await CodeActWorkerRunner.from_args(
            temporal_client=client,
            task_queue='production-queue',
            agents=[agent1, agent2],
            workflows=[SimpleAgentWorkflow, MyCustomWorkflow],
            activities=[custom_activity1, custom_activity2]
        )

        # Run worker (blocks until interrupted)
        await worker.run()
        ```
    """

    def __init__(self, worker: Worker):
        """
        Initialize the CodeActWorkerRunner with a Temporal worker.

        Args:
            worker: Configured Temporal worker instance.
        """
        super().__init__()
        self.worker = worker

    @classmethod
    async def from_args(cls,
                        temporal_client: Client,
                        task_queue: str,
                        agents: list[TemporalAgent],
                        workflows: list[type],
                        activities: list[ActivityFn] = None,
                        persistent_sandbox: DurablePersistentContainerSandbox | None = None
                        ):
        """
        Factory method to create a CodeActWorkerRunner from configuration.

        This method automatically includes:
        - SandboxWorkflow (always included)
        - All sandbox activities from DurablePersistentContainerSandbox
        - Utility activities: get_prompts, get_configs, render_jinja
        - AgentPlugin for each provided agent

        Args:
            temporal_client: Connected Temporal client instance.
            task_queue: Name of the task queue this worker will poll.
            agents: List of TemporalAgent instances to register. Each agent
                gets its own AgentPlugin for durable execution.
            workflows: List of workflow classes to register (in addition to
                SandboxWorkflow which is always included).
            activities: Optional list of additional activity functions to
                register beyond the default sandbox and utility activities.
            persistent_sandbox: Optional instance of DurablePersistentContainerSandbox

        Returns:
            CodeActWorkerRunner: Configured worker instance ready to run.

        Example:
            ```python
            worker = await CodeActWorkerRunner.from_args(
                temporal_client=client,
                task_queue='my-agents',
                agents=[simple_agent],
                workflows=[SimpleAgentWorkflow],
                activities=[]  # Optional custom activities
            )
            ```
        """
        if activities is None:
            activities = []
        default_workflows = [SandboxWorkflow]
        sandbox_activities = persistent_sandbox or DurablePersistentContainerSandbox()
        utils_activities = [get_prompts, get_configs, render_jinja]
        worker = Worker(
            temporal_client,
            task_queue=task_queue,
            workflows=default_workflows + workflows,
            activities=sandbox_activities.activities() + utils_activities + activities,
            plugins=[
                AgentPlugin(agent=agent)
                for agent in agents
            ],
        )
        return cls(worker=worker)

    async def run(self):
        """
        Run the Temporal worker.

        This method blocks until the worker is shut down (via interrupt signal
        or programmatic shutdown). The worker will continuously poll the task
        queue for workflows and activities to execute.

        Raises:
            Any exceptions from the underlying Temporal worker.

        Example:
            ```python
            worker = await CodeActWorkerRunner.from_args(...)

            # Blocks until Ctrl+C or shutdown
            await worker.run()
            ```
        """
        await self.worker.run()
