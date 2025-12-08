from typing import Optional, List

from pydantic import BaseModel, Field


class CodeActAgentDeps(BaseModel):
    container_id: str
    python_packages: Optional[List[str]] = Field(default=None, description="List of Python packages to install")
    system_packages: Optional[List[str]] = Field(default=None, description="List of system packages to install")

    model_config = {'from_attributes': True}
