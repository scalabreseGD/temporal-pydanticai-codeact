"""
Dependencies model for CodeActAgent execution context.

This module defines the runtime dependencies required by CodeActAgent
to execute code within Docker sandbox containers. These dependencies
are passed to the agent during each run.
"""

from typing import Optional, List

from pydantic import BaseModel, Field


class CodeActAgentDeps(BaseModel):
    """
    Runtime dependencies for CodeActAgent execution.

    Encapsulates the context needed for a CodeActAgent to execute code,
    including the container identifier and package requirements. This model
    is passed as the 'deps' parameter when running the agent.

    Attributes:
        container_id: ID of the Docker container where code will be executed.
            This container must be running and initialized with state management.
        python_packages: Optional list of Python packages available in the
            container. Used for documentation/context purposes in instructions.
        system_packages: Optional list of system packages installed in the
            container. Used for documentation/context purposes in instructions.

    Example:
        ```python
        deps = CodeActAgentDeps(
            container_id="abc123def456",
            python_packages=["numpy", "pandas"],
            system_packages=["git"]
        )
        result = await agent.run(
            user_prompt="Analyze this data",
            deps=deps
        )
        ```

    Note:
        Packages listed here are for informational purposes in agent instructions.
        Actual package installation is handled by the workflow via
        start_sandbox_container() and install_additional_packages().
    """
    container_id: str
    python_packages: Optional[List[str]] = Field(default=None, description="List of Python packages to install")
    system_packages: Optional[List[str]] = Field(default=None, description="List of system packages to install")

    model_config = {'from_attributes': True}
