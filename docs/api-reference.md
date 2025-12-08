# API Reference

Complete API documentation for Code Act PydanticAI. All classes and methods are documented with Google-style docstrings in the source code.

## Quick Links

- [Agents API](#agents-api)
- [Workflows API](#workflows-api)
- [Sandbox API](#sandbox-api)
- [Data Models](#data-models)
- [Activities](#activities)

---

## Agents API

Located in `src/agents/`

### BaseAgent

**File:** `src/agents/base/base_agent.py:34-154`

Abstract base class for all PydanticAI agents with Temporal integration.

#### Key Methods

```python
@classmethod
async def from_agent_confs(
    cls,
    agent_builder: AgentBuilder,
    event_stream_handler: EventStreamHandler | None = None,
    **kwargs
) -> TemporalAgent
```
Factory method to create fully configured TemporalAgent.

#### Attributes

- `agent_name: str` - Unique identifier for the agent type
- `deps_type: type[AgentDepsT]` - Type of dependencies (default: NoneType)
- `output_type: OutputSpec[OutputDataT]` - Type of agent output (default: str)

See source code documentation for complete details.

### CodeActAgent

**File:** `src/agents/base/code_act_agent.py:27-143`

Agent with code execution capabilities in Docker sandbox environments.

#### Key Features

- Dynamic instruction rendering via Jinja2
- Docker sandbox tools automatically instrumented
- Container lifecycle operations blacklisted (managed by workflow)

#### Methods

```python
def instructions(self) -> Instructions[AgentDepsT]
```
Generate dynamic instructions with Jinja2 template rendering using runtime dependencies.

**See:** Source code at `src/agents/base/code_act_agent.py:48-78` for complete documentation.

### SimpleAgent

**File:** `src/agents/simple_agent.py:15-38`

Basic code execution agent with default settings.

Minimal implementation inheriting all CodeActAgent capabilities.

---

## Workflows API

Located in `src/workflows/`

### CodeActAgentWorkflow

**File:** `src/workflows/base/codeact_agent_workflow.py:19-130`

Mixin providing container lifecycle management for workflows.

#### Methods

```python
async def start_sandbox_container(
    self,
    python_packages: Optional[List[str]] = None,
    system_packages: Optional[List[str]] = None
)
```
Start new sandbox container with specified packages. Sets `self.container_id`.

```python
async def stop_sandbox_container(self)
```
Stop and remove current sandbox container. Clears `self.container_id`.

**See:** Source code for full parameter documentation and error handling.

### SimpleAgentWorkflow

**File:** `src/workflows/simple_agent_workflow.py:22-93`

End-to-end workflow demonstrating SimpleAgent with sandbox execution.

#### Workflow Run Method

```python
@workflow.run
async def run(self, user_task: str) -> str
```

**Lifecycle:**
1. Start container with numpy and pandas
2. Load prompts and model configuration
3. Build SimpleAgent
4. Run agent with user task
5. Return output
6. Ensure container cleanup (finally block)

### SandboxWorkflow

**File:** `src/workflows/sandbox_workflow.py:18-81`

Child workflow for executing individual sandbox tasks.

#### Run Method

```python
@workflow.run
async def run(self, task: SandboxInputTask)
```

Dispatches sandbox task to corresponding activity with standard timeout and retry configuration.

---

## Sandbox API

Located in `src/docker_sandbox/`

### PersistentContainerSandbox

**File:** `src/docker_sandbox/container_sandbox.py:42-651`

Core Docker sandbox implementation with persistent Python variable state.

#### Container Lifecycle

```python
async def start_container(
    self,
    input_model: StartContainerArgs
) -> str
```
Start new container, install packages, initialize state. Returns container ID.

```python
async def stop_container(
    self,
    input_model: SandboxBaseArgs
) -> Dict[str, Any]
```
Stop and remove container. Returns success status.

#### Code Execution

```python
async def execute_python(
    self,
    input_model: ExecutePythonArgs
) -> Dict[str, Any]
```

Execute Python code with:
- Variable injection via `variables` dict
- State persistence (load → execute → save)
- Returns: `{"success": bool, "output": str, "error": str | None, "exit_code": int}`

```python
async def execute_bash(
    self,
    input_model: ExecuteBashArgs
) -> Dict[str, Any]
```

Execute bash commands. Returns same format as execute_python.

#### State Operations

```python
async def get_python_state(
    self,
    input_model: SandboxBaseArgs
) -> Dict[str, Any]
```
Get all persisted variables.

```python
async def list_state_variables(
    self,
    input_model: SandboxBaseArgs
) -> Dict[str, str]
```
List variable names with their types.

```python
async def read_state_variable(
    self,
    input_model: ReadVariableInStateArgs
) -> Dict[str, Any]
```
Read specific variable value.

```python
async def clear_python_state(
    self,
    input_model: SandboxBaseArgs
) -> Dict[str, Any]
```
Clear all persisted state.

#### File Operations

```python
async def write_file(
    self,
    input_model: WriteFileArgs
) -> Dict[str, Any]
```
Write file to container.

```python
async def read_file(
    self,
    input_model: ReadOperationsArgs
) -> Dict[str, Any]
```
Read file from container.

```python
async def list_files(
    self,
    input_model: ReadOperationsArgs
) -> Dict[str, Any]
```
List directory contents.

### DurablePersistentContainerSandbox

**File:** `src/docker_sandbox/container_sandbox.py:723-830`

Temporal-compatible version wrapping all methods as `@activity.defn`.

#### Method

```python
def activities(self) -> List[Callable]
```
Returns list of all activity methods for Temporal worker registration.

### StatelessPersistentSandbox

**File:** `src/docker_sandbox/container_sandbox.py:833-880`

Serverless sandbox adapter for instrumenting PydanticAI agents.

#### Method

```python
async def instrument_agent(
    self,
    agent: Agent,
    blacklist: Sequence[str] = None
) -> Agent
```

Convert sandbox activities into PydanticAI agent tools via child workflow execution.

**Parameters:**
- `agent`: PydanticAI Agent to instrument
- `blacklist`: Activity names to exclude

**Returns:** Instrumented agent with sandbox tools

---

## Data Models

Located in `src/datamodels/`

### Sandbox Models

**File:** `src/datamodels/sandbox.py`

#### SandboxTaskTypes (Enum)

All available sandbox operations:

```python
class SandboxTaskTypes(StrEnum):
    START_CONTAINER = 'start_container'
    STOP_CONTAINER = 'stop_container'
    RESTART_CONTAINER = 'restart_container'
    EXECUTE_PYTHON = 'execute_python'
    EXECUTE_BASH = 'execute_bash'
    GET_PYTHON_STATE = 'get_python_state'
    LIST_STATE_VARIABLES = 'list_state_variables'
    READ_STATE_VARIABLE = 'read_state_variable'
    CLEAR_PYTHON_STATE = 'clear_python_state'
    INSTALL_ADDITIONAL_PACKAGES = 'install_additional_packages'
    WRITE_FILE = 'write_file'
    READ_FILE = 'read_file'
    LIST_FILES = 'list_files'
    GET_CONTAINER_INFO = 'get_container_info'
    GET_ALL_CONTAINERS = 'get_all_containers'
    CLEANUP_CONTAINERS = 'cleanup_containers'
```

#### Argument Models

**StartContainerArgs** - Start container with packages
**ExecutePythonArgs** - Execute Python with optional variable injection and state persistence
**ExecuteBashArgs** - Execute bash commands
**WriteFileArgs** - Write file to container
**ReadOperationsArgs** - Read file or list directory
**SandboxBaseArgs** - Base arguments with container_id
**InstallAdditionalPackagesArgs** - Install packages at runtime

See source code for complete field documentation.

### Agent Models

**File:** `src/datamodels/agent_builder.py`

#### AgentBuilder

Configuration bundle for constructing agents:

```python
class AgentBuilder(BaseModel):
    prompts: dict[str, AgentPrompts]
    model_configs: dict[str, Any]
    temporal_wrapper_args: Optional[TemporalWrapperConfig]
```

#### TemporalWrapperConfig

Temporal activity configurations:

```python
class TemporalWrapperConfig(BaseModel):
    activity_config: Optional[ActivityConfig]
    model_activity_config: Optional[ActivityConfig]
    toolset_activity_config: Optional[dict[str, ActivityConfig]]
```

### CodeAct Models

**File:** `src/datamodels/codeact.py`

#### CodeActAgentDeps

Runtime dependencies for CodeActAgent:

```python
class CodeActAgentDeps(BaseModel):
    container_id: str
    python_packages: Optional[List[str]]
    system_packages: Optional[List[str]]
```

---

## Activities

Located in `src/activities/common.py`

### Configuration Activities

```python
@activity.defn
async def get_configs() -> dict[str, Any]
```
Load Temporal and LLM configuration from app_conf.yml.

```python
@activity.defn
async def get_prompts() -> Prompts
```
Load agent prompts from agent_prompts.yml.

```python
@activity.defn
async def render_jinja(
    template_str: str,
    arguments: dict[str, Any]
) -> str
```
Render Jinja2 template with provided arguments.

### Utility Functions

```python
async def get_temporal_client(
    temporal_config: Dict[str, Any],
    **kwargs
) -> Client
```
Establish Temporal client connection with Pydantic data converter.

```python
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]
```
Load configuration from YAML file with environment variable resolution.

```python
def read_prompts(path=None) -> Prompts
```
Read and parse agent prompts from YAML file.

---

## Type Definitions

### Common Types

```python
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from pydantic_ai import Agent
from temporalio import workflow, activity
from temporalio.workflow import ActivityConfig
```

### Return Types

Most sandbox operations return:

```python
Dict[str, Any] with keys:
    - "success": bool
    - "output": str  # stdout
    - "error": str | None  # stderr if failed
    - "exit_code": int  # process exit code
```

---

## See Also

- [Architecture](architecture.md) - System design and patterns
- [Sandbox Operations](sandbox-operations.md) - Detailed operation reference
- [Examples](examples.md) - Practical usage examples
- Source code docstrings for complete parameter and error documentation
