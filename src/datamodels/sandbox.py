"""
Data models for Docker sandbox operations and task management.

This module defines all input/output models for interacting with the
Docker sandbox system, including task types, argument models for various
operations, and discriminated unions for type-safe task dispatching.
"""

from enum import StrEnum
from typing import Optional, List, Dict, Any, Annotated, Literal

import pydantic
from pydantic import BaseModel, Field, TypeAdapter


class SandboxTaskTypes(StrEnum):
    """
    Enumeration of all available sandbox operations.

    Defines the complete set of operations that can be performed on
    Docker sandbox containers, including container lifecycle management,
    code execution, file operations, and state management.
    """
    START_CONTAINER = 'start_container'
    STOP_CONTAINER = 'stop_container'
    RESTART_CONTAINER = 'restart_container'
    GET_PYTHON_STATE = 'get_python_state'
    READ_STATE_VARIABLE = 'read_state_variable'
    CLEAR_PYTHON_STATE = 'clear_python_state'
    LIST_STATE_VARIABLES = 'list_state_variables'
    EXECUTE_PYTHON = 'execute_python'
    EXECUTE_BASH = 'execute_bash'
    INSTALL_ADDITIONAL_PACKAGES = 'install_additional_packages'
    WRITE_FILE = 'write_file'
    READ_FILE = 'read_file'
    LIST_FILES = 'list_files'
    GET_CONTAINER_INFO = 'get_container_info'
    GET_ALL_CONTAINERS = 'get_all_containers'
    CLEANUP_CONTAINERS = 'cleanup_containers'

    @staticmethod
    def list_tasks():
        """
        Return comma-separated list of all task type values.

        Returns:
            str: All task types joined by commas (e.g., 'start_container,stop_container,...').
        """
        return ','.join([str(element.value) for element in SandboxTaskTypes])


class SandboxBaseArgs(BaseModel):
    """
    Base arguments required for most sandbox operations.

    Provides the container_id field that most operations need. Other
    argument models inherit from or compose with this base model.

    Attributes:
        container_id: ID of the target Docker container.
        kind: Literal discriminator for Pydantic union type resolution.
    """
    container_id: str
    kind: Literal['base'] = Field(default='base')
    model_config = {'from_attributes': True}


class StartContainerArgs(BaseModel):
    """
    Arguments for starting a new sandbox container.

    Specifies packages to install during container initialization.

    Attributes:
        python_packages: List of Python packages to install via uv.
        system_packages: List of system packages to install via apt-get.
        kind: Literal discriminator for union type resolution.
    """
    python_packages: Optional[List[str]] = Field(default=None, description="List of Python packages to install")
    system_packages: Optional[List[str]] = Field(default=None, description="List of system packages to install")
    kind: Literal['start_container'] = Field(default='start_container')
    model_config = {'from_attributes': True}


class InstallAdditionalPackagesArgs(SandboxBaseArgs, StartContainerArgs):
    """
    Arguments for installing additional packages in a running container.

    Combines container_id from SandboxBaseArgs with package lists from
    StartContainerArgs to install packages at runtime.

    Attributes:
        container_id: From SandboxBaseArgs - target container.
        python_packages: From StartContainerArgs - Python packages to add.
        system_packages: From StartContainerArgs - system packages to add.
        kind: Literal discriminator for union type resolution.
    """
    kind: Literal['install_additional_packages'] = Field(default='install_additional_packages')


class ReadVariableInStateArgs(SandboxBaseArgs):
    """
    Arguments for reading a specific variable from persistent state.

    Attributes:
        container_id: Target container with the state to read.
        variable_name: Name of the variable to retrieve from state.
        kind: Literal discriminator for union type resolution.
    """
    variable_name: str
    kind: Literal['read_variable'] = Field(default='read_variable')


class ExecutePythonArgs(SandboxBaseArgs):
    """
    Arguments for executing Python code in a sandbox container.

    Supports variable injection and optional state persistence. Code runs
    in the container's Python environment with access to all installed packages.

    Attributes:
        container_id: Container where code will execute.
        code: Python code string to execute.
        variables: Optional dict of variables to inject into the execution
            environment. These become global variables in the script.
        persist_state: If True, save all non-private variables after execution.
            Defaults to True. Set to False for read-only operations.
        kind: Literal discriminator for union type resolution.
    """
    code: str
    variables: Optional[Dict[str, Any]] = Field(default=None,
                                                description="Dictionary of Python variables to be injected in the script")
    persist_state: Optional[bool] = Field(default=True,
                                          description="If true, persist state in the container. Defaults to True")
    kind: Literal['execute_python'] = Field(default='execute_python')


class ExecuteBashArgs(SandboxBaseArgs):
    """
    Arguments for executing bash commands in a sandbox container.

    Runs shell commands with bash -c in the container environment.

    Attributes:
        container_id: Container where commands will execute.
        script: Bash command string or script to execute.
        kind: Literal discriminator for union type resolution.
    """
    script: str
    kind: Literal['execute_bash'] = Field(default='execute_bash')


class ReadOperationsArgs(SandboxBaseArgs):
    """
    Arguments for file read operations in a sandbox container.

    Used for both reading file contents and listing directory contents.

    Attributes:
        container_id: Container containing the file/directory.
        path: File or directory path to read/list.
        kind: Literal discriminator for union type resolution.
    """
    path: str
    kind: Literal['read_operations'] = Field(default='read_operations')


class WriteFileArgs(SandboxBaseArgs):
    """
    Arguments for writing a file to a sandbox container.

    Creates or overwrites a file with the specified content.

    Attributes:
        container_id: Target container for the file operation.
        path: Full path where the file should be written.
        content: String content to write to the file.
        kind: Literal discriminator for union type resolution.
    """
    path: str
    content: str
    kind: Literal['write_file'] = Field(default='write_file')


SandboxTaskArgs = Annotated[
    SandboxBaseArgs | StartContainerArgs | ReadVariableInStateArgs | ExecutePythonArgs | ExecuteBashArgs | ReadOperationsArgs | WriteFileArgs | InstallAdditionalPackagesArgs,
    pydantic.Discriminator('kind')]
"""
Discriminated union of all sandbox task argument types.

Uses Pydantic's discriminator pattern with the 'kind' field to enable
type-safe parsing and validation of sandbox operation arguments.
"""

# TypeAdapter for converting dict to SandboxTaskArgs
SandboxTaskArgsAdapter = TypeAdapter(SandboxTaskArgs)
"""TypeAdapter for validating and converting dictionaries to SandboxTaskArgs."""


class SandboxInputTask(BaseModel):
    """
    Complete task specification for sandbox operations.

    Encapsulates a sandbox operation request with its task type and arguments.
    Used to dispatch tasks to the SandboxWorkflow.

    Attributes:
        task_name: The type of operation to perform (from SandboxTaskTypes enum).
        task_args: Optional arguments specific to the task type. Must match
            the task_name (e.g., ExecutePythonArgs for EXECUTE_PYTHON task).

    Example:
        ```python
        task = SandboxInputTask(
            task_name=SandboxTaskTypes.EXECUTE_PYTHON,
            task_args=ExecutePythonArgs(
                container_id="abc123",
                code="print('Hello')",
                persist_state=True
            )
        )
        ```
    """
    task_name: SandboxTaskTypes
    task_args: Optional[SandboxTaskArgs] = Field(default=None, description="Task arguments to pass to the task")
