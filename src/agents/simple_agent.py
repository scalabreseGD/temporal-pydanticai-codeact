"""
Simple code execution agent for basic tasks.

This module provides SimpleAgent, a minimal concrete implementation of
CodeActAgent with all default settings. Use this for basic code execution
tasks that don't require custom configuration.
"""
from temporalio import workflow

from datamodels.codeact import CodeActAgentOutput

with workflow.unsafe.imports_passed_through():
    from agents.base.code_act_agent import CodeActAgent


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
