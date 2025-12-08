from typing import Any, Optional

from pydantic import BaseModel, Field
from temporalio.workflow import ActivityConfig

from datamodels.prompts import AgentPrompts


class TemporalWrapperConfig(BaseModel):
    activity_config: Optional[ActivityConfig] = Field(default=None)
    model_activity_config: Optional[ActivityConfig] = Field(default=None)
    toolset_activity_config: Optional[dict[str, ActivityConfig]] = Field(default=None)


class AgentBuilder(BaseModel):
    prompts: dict[str, AgentPrompts]
    model_configs: dict[str, Any]
    temporal_wrapper_args: Optional[TemporalWrapperConfig] = Field(default=TemporalWrapperConfig())
