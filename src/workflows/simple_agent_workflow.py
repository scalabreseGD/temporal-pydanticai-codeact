"""
Example workflow demonstrating SimpleAgent with sandbox execution.

This module provides SimpleAgentWorkflow, a complete example of orchestrating
a code-executing agent with Temporal. It demonstrates the full lifecycle:
container startup, agent configuration and execution, and container cleanup.
"""

from datetime import timedelta
from typing import Any

from temporalio import workflow

from agents.simple_agent import SimpleAgent
from datamodels.agent_builder import AgentBuilder
from datamodels.codeact import CodeActAgentDeps, CodeActAgentOutput
from datamodels.prompts import AgentPrompts, Prompts
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
    async def run(self, user_task: str) -> CodeActAgentOutput | str:
        """
        Execute a user task using SimpleAgent with sandbox tools.

        Orchestrates the complete agent execution lifecycle:
        1. Starts container with numpy and pandas pre-installed
        2. Loads prompts and model configuration from activities
        3. Builds SimpleAgent with Gemini model
        4. Runs agent with user task and container dependencies
        5. Returns agent output including message, container_id, and file paths
        6. Ensures container cleanup in finally block

        Args:
            user_task: User's natural language task description.
                Example: "Load iris dataset and calculate summary statistics"

        Returns:
            CodeActAgentOutput: Agent's output containing message, container_id,
                and list of file paths available for download.

        Raises:
            ApplicationError: If container operations fail.
            WorkflowFailureError: If agent execution fails.

        Note:
            The container is always cleaned up even if the workflow fails,
            preventing resource leaks.
        """
        workflow.logger.info(f"Starting container...")
        await self.start_sandbox_container(python_packages=["numpy", "pandas"])
        workflow.logger.info(f"Started container {self.container_id}")
        try:
            prompts = await self._get_prompts()
            configs = await self._get_configs()
            gemini_configs = configs['llm']['gemini']
            agent = await SimpleAgent.from_agent_confs(
                agent_builder=AgentBuilder(prompts=prompts, model_configs=gemini_configs),
            )
            agent_output = await agent.run(
                user_prompt=user_task,
                deps=CodeActAgentDeps(container_id=self.container_id,
                                      python_packages=["numpy", "pandas"]),
                output_type=CodeActAgentOutput,
            )
            agent_final_output = agent_output.output
        except Exception as ex:
            agent_final_output = str(ex)
        finally:
            workflow.logger.info(f"Stopping container {self.container_id}")
            # await self.stop_sandbox_container()
        return agent_final_output

    @staticmethod
    async def _get_configs():
        """
        Load and extract environment variables for the workflow.

        Retrieves configuration from the get_configs activity and
        extracts MCP and LLM configuration sections.

        Returns:
            Dict containing processed environment variables for the workflow.
        """
        configs = await workflow.execute_activity(
            activity='get_configs',
            start_to_close_timeout=timedelta(minutes=1),
            result_type=dict[str, Any],
        )
        return configs

    @staticmethod
    async def _get_prompts() -> dict[str, AgentPrompts]:
        """
        Load agent prompts from configuration.

        Executes the get_prompts activity to retrieve all agent prompts
        from the YAML configuration file.

        Returns:
            Dict[str, AgentPrompts]: All agent prompts and instructions.
        """
        prompts = await workflow.execute_activity(
            activity='get_prompts',
            start_to_close_timeout=timedelta(minutes=1),
            result_type=Prompts,
        )
        return prompts.agent_prompts
