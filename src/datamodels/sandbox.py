from enum import StrEnum
from typing import Optional, List, Dict, Any, Annotated, Literal

import pydantic
from pydantic import BaseModel, Field


class SandboxTaskTypes(StrEnum):
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

    # @staticmethod
    # def exists(task_value: str) -> bool:
    #     return task_value in {item.value for item in SandboxTaskTypes}

    @staticmethod
    def list_tasks():
        return ','.join([str(element.value) for element in SandboxTaskTypes])


class SandboxBaseArgs(BaseModel):
    container_id: str
    kind: Literal['base'] = Field(default='base')


class StartContainerArgs(BaseModel):
    python_packages: Optional[List[str]] = Field(default=None, description="List of Python packages to install")
    system_packages: Optional[List[str]] = Field(default=None, description="List of system packages to install")
    kind: Literal['start_container'] = Field(default='start_container')


class ReadVariableInStateArgs(SandboxBaseArgs):
    variable_name: str
    kind: Literal['read_variable'] = Field(default='read_variable')


class ExecutePythonArgs(SandboxBaseArgs):
    code: str
    variables: Optional[Dict[str, Any]] = Field(default=None,
                                                description="Dictionary of Python variables to be injected in the script")
    persist_state: Optional[bool] = Field(default=True,
                                          description="If true, persist state in the container. Defaults to True")
    kind: Literal['execute_python'] = Field(default='execute_python')


class ExecuteBashArgs(SandboxBaseArgs):
    script: str
    kind: Literal['execute_bash'] = Field(default='execute_bash')


class ReadOperationsArgs(SandboxBaseArgs):
    path: str
    kind: Literal['read_operations'] = Field(default='read_operations')


class WriteFileArgs(SandboxBaseArgs):
    path: str
    content: str
    kind: Literal['write_file'] = Field(default='write_file')


SandboxTaskArgs = Annotated[
    SandboxBaseArgs | StartContainerArgs | ReadVariableInStateArgs | ExecutePythonArgs | ExecuteBashArgs | ReadOperationsArgs | WriteFileArgs,
    pydantic.Discriminator('kind')]


class SandboxInputTask(BaseModel):
    task_name: SandboxTaskTypes
    task_args: Optional[SandboxTaskArgs] = Field(default=None, description="Task arguments to pass to the task")


class SandboxChildWorkflowModel(SandboxBaseArgs):
    sandbox_workflow_id: str
