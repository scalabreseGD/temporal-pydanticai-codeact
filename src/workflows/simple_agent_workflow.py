"""
Example workflow demonstrating SimpleAgent with sandbox execution.

This module provides SimpleAgentWorkflow, a complete example of orchestrating
a code-executing agent with Temporal. It demonstrates the full lifecycle:
container startup, agent configuration and execution, and container cleanup.
"""

from pydantic_ai.durable_exec.temporal import TemporalAgent
from temporalio import workflow

from agents.simple_agent import SimpleAgent
from datamodels.agent_builder import AgentBuilder
from datamodels.codeact import CodeActAgentOutput
from workflows.base.codeact_agent_workflow import CodeActAgentWorkflow


@workflow.defn
class SimpleAgentWorkflow(CodeActAgentWorkflow):
    """
    End-to-end workflow for executing tasks with SimpleAgent.

    Demonstrates the complete pattern for code-executing agent workflows:
    1. Start sandbox container with required packages
    2. Load configuration (prompts, model settings)
    3. Build and run agent with sandbox tools
    4. Clean up container in finally block

    Inherits container management methods from CodeActAgentWorkflow.

    Example:
        ```python
        client = await get_temporal_client(config)
        result = await client.execute_workflow(
            'SimpleAgentWorkflow',
            arg='Calculate the mean and standard deviation of [1, 2, 3, 4, 5]',
            id='simple-agent-123',
            task_queue='my-queue'
        )
        print(result)  # Agent's output
        ```
    """

    @workflow.run
    async def run(self) -> CodeActAgentOutput | str:
        return await super().run()

    async def _get_agent(self, agent_builder: AgentBuilder) -> TemporalAgent:
        return await SimpleAgent.from_agent_confs(
            agent_builder=agent_builder,
        )
