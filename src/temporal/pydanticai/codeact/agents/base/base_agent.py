"""
Base agent utilities for building PydanticAI agents with Temporal workflows.

This module provides the foundational classes and utilities for creating AI agents
that can be executed as part of Temporal workflows. It includes:
- BaseAgent: Abstract base class for all agents
- Model configuration helpers for Gemini and Claude
- Agent delegation mechanisms for child workflows
- Code sandbox enrichment utilities

The module uses Temporal's workflow safety mechanisms to ensure proper execution
in distributed workflow contexts.
"""

from typing import Optional

from pydantic_ai._run_context import AgentDepsT
from pydantic_ai.agent import EventStreamHandler, NoneType, Instructions
from pydantic_ai.output import OutputSpec, OutputDataT
from temporalio import workflow

from temporal.pydanticai.codeact.agents.base.default_settings import DEFAULT_ACTIVITY_CONFIG, \
    default_toolset_activity_config
from temporal.pydanticai.codeact.datamodels.agent_builder import TemporalWrapperConfig, AgentBuilder

with workflow.unsafe.imports_passed_through():
    from temporal.pydanticai.codeact.datamodels.prompts import AgentPrompts

    from pydantic_ai import Agent, WrapperToolset
    from pydantic_ai.durable_exec.temporal import TemporalAgent


class BaseAgent:
    """
    Abstract base class for all PydanticAI agents in the system.

    This class provides the foundation for building AI agents that can be
    executed within Temporal workflows. It handles:
    - Model configuration (Gemini and Claude)
    - MCP toolset management
    - Agent building and wrapping for Temporal execution
    - System prompts and instructions

    Attributes:
        agent_name: The unique name identifier for the agent type.

    Subclasses must implement:
        - _get_mcp_toolsets: Define which MCP tools the agent has access to
        - _build_agent: Construct the agent with its specific configuration
    """
    agent_name: str
    deps_type: type[AgentDepsT] = NoneType
    output_type: OutputSpec[OutputDataT] = str

    def __init__(self, prompts: AgentPrompts):
        """
        Initialize the BaseAgent with configured prompts.

        Args:
            prompts: Agent-specific prompts including system prompt and instructions.
        """
        self._prompts = prompts

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return self._prompts.system_prompt

    def instructions(self, **kwargs) -> Instructions[AgentDepsT]:
        """Get the instructions for the agent, defaults to empty string if not set."""

        async def instructions_cb():
            return self._prompts.instructions or ''

        return instructions_cb

    async def _get_llm_model(self, model_configs):
        raise NotImplementedError("Must be implemented in subclass")

    @staticmethod
    async def _get_mcp_toolsets(**env_vars) -> dict[str, WrapperToolset]:
        return {}

    async def _build_agent(self,
                           agent_builder: AgentBuilder,
                           event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
                           **kwargs):
        toolsets = await self._get_mcp_toolsets(**kwargs)

        model = await self._get_llm_model(agent_builder.model_configs)
        agent = Agent(name=self.agent_name,
                      model=model,
                      toolsets=[*toolsets.values()],
                      system_prompt=self.system_prompt,
                      instructions=self.instructions(),
                      event_stream_handler=event_stream_handler,
                      deps_type=self.deps_type,
                      output_type=self.output_type
                      )

        return agent

    async def wrap_agent(self, agent: Agent,
                         temporal_wrapper_args: Optional[TemporalWrapperConfig],
                         event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
                         **kwargs) -> TemporalAgent:
        toolsets = await self._get_mcp_toolsets(**kwargs)

        temporal_agent = TemporalAgent(wrapped=agent,
                                       activity_config=temporal_wrapper_args.activity_config or DEFAULT_ACTIVITY_CONFIG,
                                       model_activity_config=temporal_wrapper_args.model_activity_config or DEFAULT_ACTIVITY_CONFIG,
                                       toolset_activity_config=temporal_wrapper_args.toolset_activity_config or default_toolset_activity_config(
                                           toolsets),
                                       event_stream_handler=event_stream_handler)
        return temporal_agent

    @classmethod
    async def from_agent_confs(cls,
                               agent_builder: AgentBuilder,
                               event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
                               **kwargs) -> TemporalAgent:
        agent_factory = cls(prompts=agent_builder.prompts[cls.agent_name])
        agent = await agent_factory._build_agent(agent_builder=agent_builder, event_stream_handler=event_stream_handler,
                                                 **kwargs)
        return await agent_factory.wrap_agent(agent=agent,
                                              temporal_wrapper_args=agent_builder.temporal_wrapper_args,
                                              event_stream_handler=event_stream_handler,
                                              **kwargs)
