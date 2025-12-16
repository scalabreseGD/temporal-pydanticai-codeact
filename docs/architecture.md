# Architecture Guide

This document explains the design and architecture of Code Act PydanticAI, including component organization, data flow, and key patterns.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Layers](#architecture-layers)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [State Management](#state-management)
- [Design Patterns](#design-patterns)

## System Overview

Code Act PydanticAI combines **PydanticAI**, **Temporal**, and **Docker** to create AI agents that can safely execute code in isolated environments with persistent state.

```
User Request
     ↓
Temporal Client
     ↓
SimpleAgentWorkflow (orchestration)
     ↓
SimpleAgent (PydanticAI)
     ↓
Sandbox Tools (execute_python, execute_bash, etc.)
     ↓
SandboxWorkflow (child workflows)
     ↓
Docker Container (isolated execution)
```

### Key Technologies

- **PydanticAI**: Type-safe agent framework with tool calling
- **Temporal**: Durable workflow orchestration with retries and recovery
- **Docker**: Container isolation for secure code execution

## Architecture Layers

The system is organized into four distinct layers:

### 1. Agent Layer

**Location:** `src/agents/`

Defines AI agents using PydanticAI. Agents have:
- System prompts and instructions
- Tool definitions (sandbox operations)
- Model configuration (Gemini)
- Event streaming handlers

**Classes:**
- `BaseAgent` - Abstract base with Temporal wrapping
- `CodeActAgent` - Adds Docker sandbox tools
- `SimpleAgent` - Concrete implementation

### 2. Workflow Layer

**Location:** `src/workflows/`

Temporal workflows orchestrate agent execution and container lifecycle.

**Components:**
- `CodeActAgentWorkflow` - Container lifecycle mixin
- `SimpleAgentWorkflow` - Full agent execution workflow
- `SandboxWorkflow` - Individual sandbox operations

### 3. Sandbox Layer

**Location:** `src/docker_sandbox/`

Three implementations providing different interfaces to the same Docker operations:

1. **PersistentContainerSandbox** - Core async methods
2. **DurablePersistentContainerSandbox** - Temporal activities
3. **StatelessPersistentSandbox** - PydanticAI agent tools

### 4. Execution Layer

Docker containers with:
- Python 3.11 + uv package manager
- Persistent state via pickle (`/tmp/sandbox_state/`)
- Resource limits (CPU, memory)
- Network isolation

## Component Details

### Agent Architecture

```
┌─────────────────────────────────────────────┐
│           BaseAgent (Abstract)               │
│  - Model configuration (Gemini/Claude)      │
│  - MCP toolset management                   │
│  - Temporal agent wrapping                  │
│  - System prompt + instructions             │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────▼────────────┐
        │    CodeActAgent       │
        │  - Jinja2 instructions│
        │  - Sandbox tools      │
        │  - Blacklist lifecycle│
        └──────────┬────────────┘
                   │
        ┌──────────▼────────────┐
        │    SimpleAgent        │
        │  - Default settings   │
        │  - Basic usage        │
        └───────────────────────┘
```

**Key Methods:**
- `from_agent_confs()` - Factory method to build and wrap agent
- `_build_agent()` - Construct PydanticAI agent
- `wrap_agent()` - Wrap for Temporal execution
- `_get_mcp_toolsets()` - Load MCP tools (extensibility point)

### Workflow Architecture

```
┌─────────────────────────────────────────────┐
│      CodeActAgentWorkflow (Mixin)           │
│  - start_sandbox_container()                │
│  - stop_sandbox_container()                 │
│  - container_id: str | None                 │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────▼────────────┐
        │ SimpleAgentWorkflow   │
        │  @workflow.run        │
        │  1. Start container   │
        │  2. Load config       │
        │  3. Build agent       │
        │  4. Run agent         │
        │  5. Stop container    │
        └───────────────────────┘
```

### Sandbox Architecture

```
┌────────────────────────────────────────────────┐
│     PersistentContainerSandbox (Core)          │
│  - Docker client management                    │
│  - Container lifecycle (start/stop/restart)    │
│  - Code execution (python/bash)                │
│  - State operations (get/set/clear)            │
│  - File operations (read/write/list)           │
└────────────────┬───────────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │DurablePersistent...     │
    │  @activity.defn on all  │
    │  methods for Temporal   │
    └────────────┬────────────┘
                 │
    ┌────────────▼────────────┐
    │StatelessPersistent...   │
    │  Convert activities to  │
    │  agent tools via child  │
    │  workflow execution     │
    └─────────────────────────┘
```

## Data Flow

### Agent Execution Flow

1. **Workflow Start**
   ```
   Client → execute_workflow('SimpleAgentWorkflow', arg=task)
   ```

2. **Container Setup**
   ```
   Workflow → start_sandbox_container(python_packages)
   Activity → Docker.containers.run()
   Activity → install packages via uv
   Activity → initialize state (init_state.py)
   ```

3. **Agent Initialization**
   ```
   Workflow → Load prompts from activity
   Workflow → Load model config from activity
   Workflow → Build SimpleAgent with sandbox tools
   ```

4. **Agent Execution**
   ```
   Workflow → agent.run(user_prompt, deps=CodeActAgentDeps)
   Agent → Model generates tool calls
   Agent → Call execute_python tool
   Tool → Start child SandboxWorkflow
   SandboxWorkflow → execute_python activity
   Activity → Docker exec with load_state + code + save_state
   Container → Execute Python with persisted variables
   ```

5. **Cleanup**
   ```
   Workflow (finally) → stop_sandbox_container()
   Activity → container.stop() + container.remove()
   ```

### Tool Call Flow

When an agent calls `execute_python`:

```
1. Agent Tool Call
   execute_python(container_id="abc", code="x=42")

2. StatelessPersistentSandbox Tool
   Creates SandboxInputTask

3. Child Workflow
   await client.execute_workflow(
       'SandboxWorkflow',
       arg=SandboxInputTask(
           task_name='execute_python',
           task_args=ExecutePythonArgs(...)
       )
   )

4. SandboxWorkflow
   await workflow.execute_activity(
       activity='execute_python',
       arg=ExecutePythonArgs(...)
   )

5. DurablePersistentContainerSandbox Activity
   @activity.defn
   async def execute_python(input_model)

6. PersistentContainerSandbox Core
   container.exec_run([
       "python", "-c",
       load_state + user_code + save_state
   ])

7. Return Result
   {"success": True, "output": "...", "error": None}
```

## State Management

### Persistence Mechanism

Variables persist across executions using pickle serialization:

```
┌─────────────────────────────────────────┐
│  /tmp/sandbox_state/globals.pkl         │
│  {                                      │
│    "x": 42,                             │
│    "data": [1, 2, 3],                   │
│    "result": {"mean": 2.0}             │
│  }                                      │
└─────────────────────────────────────────┘
```

### Execution Lifecycle

**Before Execution:**
```python
# load_state.py injected at start
import pickle
with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
    _state = pickle.load(f)
globals().update(_state)  # Restore variables
```

**User Code:**
```python
# Your code runs with restored variables
print(x)  # x = 42 from previous execution
y = x * 2
```

**After Execution:**
```python
# save_state.py injected at end
state_to_save = {
    k: v for k, v in globals().items()
    if not k.startswith('_')  # Exclude private
    and not callable(v)        # Exclude functions
    and is_picklable(v)        # Only picklable
}
pickle.dump(state_to_save, f)
```

### State Operations

| Operation | Script | Description |
|-----------|--------|-------------|
| `init_state` | `init_state.py` | Create empty state file |
| `get_python_state` | `get_state.py` | Get all variables |
| `list_state_variables` | `list_variables.py` | List var names + types |
| `read_state_variable` | `read_variable.py` | Get specific variable |
| `clear_python_state` | `clear_state.py` | Reset to empty state |

## Design Patterns

### 1. Mixin Pattern

`CodeActAgentWorkflow` is a mixin providing container management:

```python
class CodeActAgentWorkflow:
    def __init__(self):
        self.container_id: str | None = None

    async def start_sandbox_container(self, ...):
        self.container_id = await workflow.execute_activity(...)

    async def stop_sandbox_container(self):
        await workflow.execute_activity(...)
        self.container_id = None

@workflow.defn
class SimpleAgentWorkflow(CodeActAgentWorkflow):
    @workflow.run
    async def run(self, task: str) -> str:
        await self.start_sandbox_container()
        try:
            # Use self.container_id
            return await agent.run(...)
        finally:
            await self.stop_sandbox_container()
```

### 2. Factory Pattern

`from_agent_confs()` creates fully configured agents:

```python
agent = await SimpleAgent.from_agent_confs(
    agent_builder=AgentBuilder(
        prompts=prompts,
        model_configs=config
    )
)
```

### 3. Adapter Pattern

`StatelessPersistentSandbox` adapts activities to agent tools:

```python
# Activity → Agent Tool
def __create_tool(activity_name, input_type, return_type):
    async def tool_func(ctx, input_model):
        return await activity.client().execute_workflow(
            'SandboxWorkflow',
            arg=SandboxInputTask(
                task_name=activity_name,
                task_args=input_model
            )
        )
    return tool_func
```

### 4. Discriminated Unions

Type-safe task dispatching with Pydantic:

```python
SandboxTaskArgs = Annotated[
    SandboxBaseArgs
    | StartContainerArgs
    | ExecutePythonArgs
    | ...,
    pydantic.Discriminator('kind')
]

task = SandboxInputTask(
    task_name=SandboxTaskTypes.EXECUTE_PYTHON,
    task_args=ExecutePythonArgs(
        container_id="abc",
        code="print('hello')",
        kind='execute_python'  # Discriminator
    )
)
```

### 5. Template Method

`BaseAgent._build_agent()` defines the agent construction template:

```python
class BaseAgent:
    async def _build_agent(self, agent_builder, ...):
        toolsets = await self._get_mcp_toolsets()  # Hook
        model = await self._get_gemini_model()
        agent = Agent(
            name=self.agent_name,
            model=model,
            toolsets=[*toolsets.values()],
            system_prompt=self.system_prompt,
            instructions=self.instructions()
        )
        return agent


class CodeActAgent(BaseAgent):
    async def _build_agent(self, ...):
        base_agent = await super()._build_agent(...)
        # Customize: add sandbox tools
        return await sandbox.code_sandbox_tools(base_agent)
```

## Scalability Considerations

### Horizontal Scaling

- **Workers**: Run multiple workers on different machines
- **Task Queues**: Partition work by queue
- **Containers**: Each workflow gets its own container

### Resource Management

- **Container Limits**: Memory and CPU constraints per container
- **Cleanup**: Automatic container removal after workflow completion
- **Image Caching**: Docker image built once, reused for all containers

### Temporal Benefits

- **Durability**: Workflows survive worker crashes/restarts
- **Retries**: Automatic retry with exponential backoff
- **Versioning**: Deploy new code without affecting running workflows
- **Observability**: Full execution history and replay capability

## See Also

- [Getting Started](getting-started.md) - Step-by-step tutorial
- [API Reference](api-reference.md) - Complete API documentation
- [Sandbox Operations](sandbox-operations.md) - All sandbox operations
- [Examples](examples.md) - Practical usage patterns
