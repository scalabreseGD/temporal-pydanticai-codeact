"""
Data models for serialized custom functions.

This module provides models for serializing Python functions defined in the codebase
so they can be injected into sandbox execution environments with automatic dependency
detection and installation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SerializedFunction(BaseModel):
    """
    Represents a serialized Python function with metadata.

    Contains the function's source code, detected dependencies, and metadata
    needed to inject it into a sandbox execution environment.
    """

    name: str = Field(
        description="The function name"
    )

    source_code: str = Field(
        description="Complete function source code extracted via inspect.getsource()"
    )

    dependencies: List[str] = Field(
        default_factory=list,
        description="List of top-level package dependencies detected from imports (e.g., ['pandas', 'numpy'])"
    )

    is_async: bool = Field(
        default=False,
        description="Whether the function is async"
    )

    signature: Optional[str] = Field(
        default=None,
        description="Function signature as a string for documentation purposes"
    )

    docstring: Optional[str] = Field(
        default=None,
        description="Function docstring"
    )


class CustomFunctionsConfig(BaseModel):
    """
    Container for multiple serialized functions.

    Used to pass a collection of custom functions to sandbox execution or
    agent configuration.
    """

    functions: List[SerializedFunction] = Field(
        default_factory=list,
        description="List of serialized functions"
    )

    def get_all_dependencies(self) -> List[str]:
        """
        Get unique list of all dependencies across all functions.

        Returns:
            Deduplicated list of package names
        """
        deps = set()
        for func in self.functions:
            deps.update(func.dependencies)
        return sorted(list(deps))

    def get_function_by_name(self, name: str) -> Optional[SerializedFunction]:
        """
        Retrieve a function by name.

        Args:
            name: Function name to search for

        Returns:
            SerializedFunction if found, None otherwise
        """
        for func in self.functions:
            if func.name == name:
                return func
        return None

    def get_all_signatures(self) -> List[str]:
        """
        Get all function signatures for documentation.

        Returns:
            List of function signature strings
        """
        return [f.signature for f in self.functions if f.signature]
