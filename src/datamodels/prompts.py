"""
Data models for agent prompts and instructions.

This module defines the structure for agent system prompts and instructions
that are loaded from YAML configuration files.
"""

from pydantic import BaseModel, Field


class AgentPrompts(BaseModel):
    """
    Container for agent-specific prompts.

    Attributes:
        system_prompt: The system-level prompt defining agent behavior.
        instructions: Additional instructions for the agent.
    """
    system_prompt: str | None = Field(None)
    instructions: str | None = Field(None)


class Prompts(BaseModel):
    """
    Collection of prompts for all agents.

    Attributes:
        agent_prompts: Dictionary mapping agent names to their prompts.
    """
    agent_prompts: dict[str, AgentPrompts]
