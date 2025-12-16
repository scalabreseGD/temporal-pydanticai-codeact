"""
Simple code execution agent for basic tasks.

This module provides SimpleAgent, a minimal concrete implementation of
CodeActAgent with all default settings. Use this for basic code execution
tasks that don't require custom configuration.
"""
from pydantic_ai import WrapperToolset
from pydantic_ai.mcp import MCPServerStdio
from temporalio import workflow

from temporal.pydanticai.codeact.datamodels.codeact import CodeActAgentOutput

with workflow.unsafe.imports_passed_through():
    from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
    from pydantic_ai.providers.google import GoogleProvider
    from temporal.pydanticai.codeact.agents.base.code_act_agent import CodeActAgent


class SimpleAgent(CodeActAgent):
    """
    Basic code execution agent with default settings.

    A minimal implementation of CodeActAgent that inherits all code execution
    capabilities without additional customization. Suitable for simple use cases
    where standard code execution, file operations, and state management are
    sufficient.

    Attributes:
        agent_name: Fixed identifier 'simple_agent' for this agent type.

    Example:
        ```python
        agent = await SimpleAgent.from_agent_confs(
            agent_builder=AgentBuilder(prompts=prompts, model_configs=config)
        )
        result = await agent.run(
            user_prompt="Calculate the mean of [1, 2, 3, 4, 5]",
            deps=CodeActAgentDeps(container_id=container_id)
        )
        ```
    """
    agent_name = 'simple_agent'
    output_type = CodeActAgentOutput

    @staticmethod
    async def _get_mcp_toolsets(**env_vars) -> dict[str, WrapperToolset]:
        fetch_mcp = MCPServerStdio("uvx", ["mcp-server-fetch", "--ignore-robots-txt"]).filtered(
            lambda ctx, tool_def: True)
        return {'fetch': fetch_mcp}

    async def _get_llm_model(self, model_configs):
        """
        Create and configure a Google Gemini language model.

        Args:
            **model_configs: Configuration variables including:
                - api_key: API key for Google Gemini
                - model_name: The gemini model name
                - settings: GoogleModelSettings dict

        Returns:
            GoogleModel: Configured Gemini model instance.
        """
        api_key = model_configs.get('api_key')
        model_name = model_configs.get('model_name', 'gemini-2.5-pro')
        if 'settings' in model_configs:
            settings = model_configs.get('settings')
        else:
            settings = dict()
        model = GoogleModel(
            model_name=model_name,
            provider=GoogleProvider(api_key=api_key),
            settings=GoogleModelSettings(**settings)
        )
        return model
