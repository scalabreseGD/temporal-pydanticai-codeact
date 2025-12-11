"""
Unit tests for agent builder data models.

Tests AgentBuilder and TemporalWrapperConfig models in
src/datamodels/agent_builder.py.
"""

import pytest
from pydantic import ValidationError
from temporalio.workflow import ActivityConfig

from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder, TemporalWrapperConfig
from temporal.pydanticai.codeact.datamodels.prompts import AgentPrompts


@pytest.mark.unit
class TestTemporalWrapperConfig:
    """Test TemporalWrapperConfig model."""

    def test_empty_config(self):
        """Test creating empty TemporalWrapperConfig."""
        config = TemporalWrapperConfig()
        assert config.activity_config is None
        assert config.model_activity_config is None
        assert config.toolset_activity_config is None

    def test_with_activity_config(self):
        """Test with basic activity configuration."""
        activity_cfg = ActivityConfig(
            start_to_close_timeout="30s", retry_policy=None
        )
        config = TemporalWrapperConfig(activity_config=activity_cfg)
        assert config.activity_config == activity_cfg
        assert config.model_activity_config is None

    def test_with_model_activity_config(self):
        """Test with model activity configuration."""
        model_cfg = ActivityConfig(start_to_close_timeout="60s")
        config = TemporalWrapperConfig(model_activity_config=model_cfg)
        assert config.model_activity_config == model_cfg
        assert config.activity_config is None

    def test_with_toolset_activity_config(self):
        """Test with toolset activity configuration."""
        toolset_cfg = {
            "execute_python": ActivityConfig(start_to_close_timeout="120s"),
            "execute_bash": ActivityConfig(start_to_close_timeout="90s"),
        }
        config = TemporalWrapperConfig(toolset_activity_config=toolset_cfg)
        assert config.toolset_activity_config == toolset_cfg
        assert len(config.toolset_activity_config) == 2

    def test_with_all_configs(self):
        """Test with all configuration types."""
        activity_cfg = ActivityConfig(start_to_close_timeout="30s")
        model_cfg = ActivityConfig(start_to_close_timeout="60s")
        toolset_cfg = {
            "tool1": ActivityConfig(start_to_close_timeout="45s"),
        }

        config = TemporalWrapperConfig(
            activity_config=activity_cfg,
            model_activity_config=model_cfg,
            toolset_activity_config=toolset_cfg,
        )

        assert config.activity_config == activity_cfg
        assert config.model_activity_config == model_cfg
        assert config.toolset_activity_config == toolset_cfg


@pytest.mark.unit
class TestAgentBuilder:
    """Test AgentBuilder model."""

    def test_minimal_valid_creation(self, test_prompts):
        """Test creating with minimal required fields."""
        prompts_dict = {
            "test_agent": AgentPrompts(
                system_prompt=test_prompts["test_agent"]["system_prompt"],
                instructions=test_prompts["test_agent"]["instructions"],
            )
        }
        model_configs = {"gemini": {"api_key": "test_key", "model_name": "gemini-pro"}}

        builder = AgentBuilder(prompts=prompts_dict, model_configs=model_configs)

        assert builder.prompts == prompts_dict
        assert builder.model_configs == model_configs
        assert builder.temporal_wrapper_args is None

    def test_with_temporal_wrapper_args(self, test_prompts):
        """Test creating with Temporal wrapper configuration."""
        prompts_dict = {
            "test_agent": AgentPrompts(
                system_prompt=test_prompts["test_agent"]["system_prompt"],
                instructions=test_prompts["test_agent"]["instructions"],
            )
        }
        model_configs = {"gemini": {"api_key": "test_key"}}
        temporal_cfg = TemporalWrapperConfig(
            activity_config=ActivityConfig(start_to_close_timeout="30s")
        )

        builder = AgentBuilder(
            prompts=prompts_dict,
            model_configs=model_configs,
            temporal_wrapper_args=temporal_cfg,
        )

        assert builder.prompts == prompts_dict
        assert builder.model_configs == model_configs
        assert builder.temporal_wrapper_args == temporal_cfg

    def test_multiple_agent_prompts(self):
        """Test with multiple agent configurations."""
        prompts_dict = {
            "agent1": AgentPrompts(
                system_prompt="System prompt 1", instructions="Instructions 1"
            ),
            "agent2": AgentPrompts(
                system_prompt="System prompt 2", instructions="Instructions 2"
            ),
            "agent3": AgentPrompts(
                system_prompt="System prompt 3", instructions="Instructions 3"
            ),
        }
        model_configs = {"model1": {"setting": "value"}}

        builder = AgentBuilder(prompts=prompts_dict, model_configs=model_configs)

        assert len(builder.prompts) == 3
        assert "agent1" in builder.prompts
        assert "agent2" in builder.prompts
        assert "agent3" in builder.prompts

    def test_complex_model_configs(self, test_prompts):
        """Test with complex model configurations."""
        prompts_dict = {
            "test_agent": AgentPrompts(
                system_prompt=test_prompts["test_agent"]["system_prompt"],
                instructions=test_prompts["test_agent"]["instructions"],
            )
        }
        model_configs = {
            "gemini": {
                "api_key": "test_key",
                "model_name": "gemini-2.5-pro",
                "settings": {"temperature": 0.7, "max_tokens": 4096, "top_p": 0.9},
            },
            "anthropic": {
                "api_key": "another_key",
                "model_name": "claude-3-sonnet",
                "settings": {"temperature": 0.5},
            },
        }

        builder = AgentBuilder(prompts=prompts_dict, model_configs=model_configs)

        assert len(builder.model_configs) == 2
        assert "gemini" in builder.model_configs
        assert "anthropic" in builder.model_configs
        assert builder.model_configs["gemini"]["settings"]["temperature"] == 0.7

    def test_missing_prompts_fails(self):
        """Test that missing prompts fails validation."""
        with pytest.raises(ValidationError):
            AgentBuilder(model_configs={"test": {}})

    def test_missing_model_configs_fails(self, test_prompts):
        """Test that missing model_configs fails validation."""
        prompts_dict = {
            "test_agent": AgentPrompts(
                system_prompt=test_prompts["test_agent"]["system_prompt"],
                instructions=test_prompts["test_agent"]["instructions"],
            )
        }
        with pytest.raises(ValidationError):
            AgentBuilder(prompts=prompts_dict)

    def test_model_serialization(self, test_prompts):
        """Test model can be serialized."""
        prompts_dict = {
            "test_agent": AgentPrompts(
                system_prompt=test_prompts["test_agent"]["system_prompt"],
                instructions=test_prompts["test_agent"]["instructions"],
            )
        }
        model_configs = {"gemini": {"api_key": "test_key"}}

        builder = AgentBuilder(prompts=prompts_dict, model_configs=model_configs)
        data = builder.model_dump()

        assert "prompts" in data
        assert "model_configs" in data
        assert "test_agent" in data["prompts"]
