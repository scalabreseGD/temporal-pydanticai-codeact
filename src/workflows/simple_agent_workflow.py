from datetime import timedelta
from typing import Any

from temporalio import workflow

from agents.simple_agent import SimpleAgent
from datamodels.agent_builder import AgentBuilder
from datamodels.prompts import AgentPrompts, Prompts
from workflows.base.codeact_agent_workflow import CodeActAgentWorkflow


@workflow.defn
class SimpleAgentWorkflow(CodeActAgentWorkflow):

    @workflow.run
    async def run(self, user_task: str) -> str:
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
            )
            return agent_output.output
        finally:
            workflow.logger.info(f"Stopping container {self.container_id}")
            await self.stop_sandbox_container()

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
