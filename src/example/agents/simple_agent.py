"""
Simple code execution agent for basic tasks.

This module provides SimpleAgent, a minimal concrete implementation of
CodeActAgent with all default settings. Use this for basic code execution
tasks that don't require custom configuration.
"""

from pydantic_ai import WrapperToolset, RetryPromptPart
from pydantic_ai.exceptions import ToolRetryError
from pydantic_ai.mcp import MCPServerStdio
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporal.pydanticai.codeact.datamodels.codeact import CodeActAgentOutput
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

    @staticmethod
    async def _get_custom_functions(**kwargs) -> list:
        return [SimpleAgent.duckduckgo_text_search]

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

    @staticmethod
    async def duckduckgo_text_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
        from duckduckgo_search import DDGS
        """
            Performs a text search using DuckDuckGo and returns a list of results with the format:
                {
                    'title': Page Title,
                    'url': The URL of the page,
                    'preview': The first 100 characters of the page,
                }

            Args:
                query (str): The search term.
                max_results (int): The maximum number of results to return.
                
            Returns:
                list[dict[str, str]]: A list of search results dictionaries.
            """

        # Initialize the DDGS object (DuckDuckGo Search)
        ddgs = DDGS()

        # Perform the text search
        # The 'text' method returns a generator of results
        try:
            search_results = ddgs.text(
                keywords=query,
                region='us-en',  # Example region
                max_results=max_results
            )

            results_list = list(search_results)

            if not results_list:
                return []

            result_dicts = []
            for result in results_list:
                result_dicts.append({
                    'title': result.get('title'),
                    'url': result.get('href'),
                    'preview': result.get('body', '')[:100],
                })

            return result_dicts
        except Exception as e:
            raise ToolRetryError(tool_retry=RetryPromptPart(content=str(e)))
