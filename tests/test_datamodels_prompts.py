"""
Unit tests for prompts data models.

Tests AgentPrompts and Prompts models in src/datamodels/prompts.py.
"""

import pytest
from pydantic import ValidationError

from datamodels.prompts import AgentPrompts, Prompts


@pytest.mark.unit
class TestAgentPrompts:
    """Test AgentPrompts model."""

    def test_valid_creation(self):
        """Test creating valid AgentPrompts."""
        prompts = AgentPrompts(
            system_prompt="You are a helpful assistant.",
            instructions="Use the tools to complete tasks.",
        )
        assert prompts.system_prompt == "You are a helpful assistant."
        assert prompts.instructions == "Use the tools to complete tasks."

    def test_multiline_prompts(self):
        """Test with multiline prompts."""
        system = """You are an expert data scientist.
        You have access to Python and data analysis tools.
        Always explain your methodology."""

        instructions = """Container ID: {{ container_id }}
        Packages: {{ python_packages }}

        Follow these steps:
        1. Analyze the data
        2. Create visualizations
        3. Provide insights"""

        prompts = AgentPrompts(system_prompt=system, instructions=instructions)
        assert "data scientist" in prompts.system_prompt
        assert "{{ container_id }}" in prompts.instructions

    def test_with_jinja_templates(self):
        """Test prompts with Jinja2 template syntax."""
        instructions = """
        Container: {{ container_id }}
        {% if python_packages %}
        Installed packages: {{ python_packages | join(', ') }}
        {% endif %}
        """
        prompts = AgentPrompts(
            system_prompt="System prompt", instructions=instructions
        )
        assert "{{" in prompts.instructions
        assert "{%" in prompts.instructions

    def test_empty_system_prompt_fails(self):
        """Test that empty system_prompt fails validation."""
        with pytest.raises(ValidationError):
            AgentPrompts(system_prompt="", instructions="Some instructions")

    def test_empty_instructions_fails(self):
        """Test that empty instructions fails validation."""
        with pytest.raises(ValidationError):
            AgentPrompts(system_prompt="System prompt", instructions="")

    def test_missing_system_prompt_fails(self):
        """Test that missing system_prompt fails validation."""
        with pytest.raises(ValidationError):
            AgentPrompts(instructions="Some instructions")

    def test_missing_instructions_fails(self):
        """Test that missing instructions fails validation."""
        with pytest.raises(ValidationError):
            AgentPrompts(system_prompt="System prompt")

    def test_whitespace_only_fails(self):
        """Test that whitespace-only strings fail validation."""
        with pytest.raises(ValidationError):
            AgentPrompts(system_prompt="   ", instructions="Some instructions")

        with pytest.raises(ValidationError):
            AgentPrompts(system_prompt="System prompt", instructions="   ")

    def test_model_serialization(self):
        """Test model can be serialized to dict."""
        prompts = AgentPrompts(
            system_prompt="Test system", instructions="Test instructions"
        )
        data = prompts.model_dump()
        assert data["system_prompt"] == "Test system"
        assert data["instructions"] == "Test instructions"

    def test_model_deserialization(self):
        """Test model can be created from dict."""
        data = {
            "system_prompt": "Deserialized system",
            "instructions": "Deserialized instructions",
        }
        prompts = AgentPrompts(**data)
        assert prompts.system_prompt == "Deserialized system"
        assert prompts.instructions == "Deserialized instructions"


@pytest.mark.unit
class TestPrompts:
    """Test Prompts model (root dict of agent prompts)."""

    def test_empty_prompts(self):
        """Test creating empty Prompts."""
        prompts = Prompts(root={})
        assert len(prompts.root) == 0

    def test_single_agent_prompts(self):
        """Test with single agent configuration."""
        agent_prompts = AgentPrompts(
            system_prompt="System", instructions="Instructions"
        )
        prompts = Prompts(root={"simple_agent": agent_prompts})

        assert len(prompts.root) == 1
        assert "simple_agent" in prompts.root
        assert prompts.root["simple_agent"].system_prompt == "System"

    def test_multiple_agent_prompts(self):
        """Test with multiple agent configurations."""
        agents = {
            "agent1": AgentPrompts(system_prompt="System 1", instructions="Inst 1"),
            "agent2": AgentPrompts(system_prompt="System 2", instructions="Inst 2"),
            "agent3": AgentPrompts(system_prompt="System 3", instructions="Inst 3"),
        }
        prompts = Prompts(root=agents)

        assert len(prompts.root) == 3
        assert all(key in prompts.root for key in ["agent1", "agent2", "agent3"])

    def test_dict_access(self):
        """Test dictionary-style access to prompts."""
        agent_prompts = AgentPrompts(
            system_prompt="System", instructions="Instructions"
        )
        prompts = Prompts(root={"test_agent": agent_prompts})

        # Access via root
        assert prompts.root["test_agent"].system_prompt == "System"

    def test_model_serialization(self):
        """Test Prompts can be serialized."""
        agents = {
            "agent1": AgentPrompts(system_prompt="S1", instructions="I1"),
            "agent2": AgentPrompts(system_prompt="S2", instructions="I2"),
        }
        prompts = Prompts(root=agents)
        data = prompts.model_dump()

        assert "root" in data
        assert "agent1" in data["root"]
        assert "agent2" in data["root"]

    def test_model_deserialization(self):
        """Test Prompts can be created from dict."""
        data = {
            "root": {
                "agent1": {"system_prompt": "S1", "instructions": "I1"},
                "agent2": {"system_prompt": "S2", "instructions": "I2"},
            }
        }
        prompts = Prompts(**data)

        assert len(prompts.root) == 2
        assert isinstance(prompts.root["agent1"], AgentPrompts)
        assert prompts.root["agent1"].system_prompt == "S1"

    def test_complex_agent_names(self):
        """Test with various agent name formats."""
        agents = {
            "simple_agent": AgentPrompts(system_prompt="S1", instructions="I1"),
            "data-science-agent": AgentPrompts(system_prompt="S2", instructions="I2"),
            "CodeAgent123": AgentPrompts(system_prompt="S3", instructions="I3"),
            "agent.with.dots": AgentPrompts(system_prompt="S4", instructions="I4"),
        }
        prompts = Prompts(root=agents)

        assert len(prompts.root) == 4
        assert all(
            key in prompts.root
            for key in [
                "simple_agent",
                "data-science-agent",
                "CodeAgent123",
                "agent.with.dots",
            ]
        )
