"""
Configuration models for building PydanticAI agents with Temporal integration.

This module provides Pydantic models for configuring agent creation, including
prompts, model settings, and Temporal activity configurations for durable
execution.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field
from temporalio.workflow import ActivityConfig

from temporal.pydanticai.codeact.datamodels.prompts import AgentPrompts


class TemporalWrapperConfig(BaseModel):
    """
    Configuration for Temporal activity timeouts and retries.

    Defines activity configurations for different types of operations when
    wrapping a PydanticAI agent for Temporal workflow execution. Allows
    customization of timeouts and retry policies for general activities,
    model calls, and individual toolsets.

    Attributes:
        activity_config: Configuration for general agent activities.
            Defaults to DEFAULT_ACTIVITY_CONFIG if not specified.
        model_activity_config: Configuration for LLM model calls.
            Defaults to DEFAULT_ACTIVITY_CONFIG if not specified.
        toolset_activity_config: Per-toolset activity configurations.
            Maps toolset IDs to their specific ActivityConfig.
            Defaults to default_toolset_activity_config if not specified.
    """
    activity_config: Optional[ActivityConfig] = Field(default=None)
    model_activity_config: Optional[ActivityConfig] = Field(default=None)
    toolset_activity_config: Optional[dict[str, ActivityConfig]] = Field(default=None)


class AgentBuilder(BaseModel):
    """
    Complete configuration bundle for constructing an agent.

    Aggregates all configuration needed to build and wrap a PydanticAI agent:
    prompts, model settings, and Temporal wrapper configuration. Used by
    agent factory methods like BaseAgent.from_agent_confs().

    Attributes:
        prompts: Dictionary mapping agent names to their AgentPrompts
            (system_prompt and instructions).
        model_configs: Dictionary containing model-specific configuration.
            For Gemini: {'api_key', 'model_name', 'settings'}.
            For other models: provider-specific configuration.
        temporal_wrapper_args: Optional Temporal activity configurations.
            Defaults to TemporalWrapperConfig with default settings.

    Example:
        ```python
        builder = AgentBuilder(
            prompts={
                'simple_agent': AgentPrompts(
                    system_prompt="You are a Python coding assistant",
                    instructions="Use the sandbox to execute code"
                )
            },
            model_configs={
                'api_key': 'your-api-key',
                'model_name': 'gemini-2.5-pro'
            }
        )
        agent = await SimpleAgent.from_agent_confs(builder)
        ```
    """
    prompts: dict[str, AgentPrompts]
    model_configs: dict[str, Any]
    temporal_wrapper_args: Optional[TemporalWrapperConfig] = Field(default=TemporalWrapperConfig())