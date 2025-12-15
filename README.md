# temporal.pydanticai.codeact

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A reusable library for building intelligent agents with safe code execution capabilities using PydanticAI, Temporal workflows, and Docker sandboxes.

## Overview

**temporal.pydanticai.codeact** is a Python library that combines three powerful technologies to create AI agents that can write and execute code safely in isolated environments with persistent state:

- **[PydanticAI](https://ai.pydantic.dev/)** (v1.27.0+) - Type-safe agent framework from Anthropic for building production-grade GenAI applications
- **[Temporal](https://temporal.io/)** (v1.19.0+) - Workflow orchestration for reliable, durable, long-running agent processes
- **[Docker](https://www.docker.com/)** - Containerized execution environment for secure code isolation

### Key Features

✨ **Crash-Resistant Persistence** - Docker volumes ensure Python variables and files survive crashes and restarts
🔒 **Sandboxed Security** - All code runs in isolated Docker containers with resource limits
🔄 **Durable Workflows** - Temporal ensures reliable execution with automatic retries and recovery
🎯 **Type-Safe** - Full Pydantic validation for all inputs and outputs
🛠️ **Flexible Tools** - Agents can execute Python, run bash commands, manage files, and query state
📦 **Dynamic Packages** - Install Python and system packages on-demand during execution
🔌 **MCP Integration** - Native support for Model Context Protocol servers as agent tools
🌐 **Multi-Host Support** - Optional NFS volumes for shared state across multiple workers
🎨 **Extensible Design** - Easy to create custom agents with specialized capabilities

## Quick Start

### Prerequisites

- **Python 3.13+**
- **Docker** (running daemon)
- **Temporal Server** (local dev server or cloud)
- **uv** package manager

### Installation

#### For Library Users (Using in Your Project)

Install the published library in your project:

```bash
# Install from PyPI (when published)
pip install temporal-pydanticai-codeact

# Or with uv
uv add temporal-pydanticai-codeact

# Or with poetry
poetry add temporal-pydanticai-codeact
```

Then use it in your code:

```python
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent
from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner
from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder

# Your code here...
```

#### For Contributors (Development Setup)

```bash
# Clone and install for development
git clone https://github.com/scalabreseGD/temporal-pydanticai-codeact.git
cd temporal-pydanticai-codeact

# Install with uv (recommended)
uv sync

# Or install in editable mode with pip
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
```

### Configuration

Create `app_conf.yml` in the project root:

```yaml
temporal:
  url: localhost:7233
  namespace: default

llm:
  gemini:
    api_key: YOUR_GEMINI_API_KEY
    model_name: gemini-2.5-pro
```

Create `agent_prompts.yml`:

```yaml
simple_agent:
  system_prompt: "You are a Python coding assistant with access to a sandboxed execution environment."
  instructions: |
    You have access to a Docker container (ID: {{ container_id }}) with these packages: {{ python_packages }}.
    Use the execute_python tool to run code and solve the user's task.
```

### Basic Usage

```python
import asyncio
from temporal.pydanticai.codeact.activities.common import load_config, get_temporal_client
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent
from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
from temporal.pydanticai.codeact.workflows.simple_agent_workflow import SimpleAgentWorkflow
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

async def main():
    # Connect to Temporal
    config = load_config()
    client = await get_temporal_client(
        config['temporal'],
        plugins=[PydanticAIPlugin()]
    )

    # Execute workflow
    result = await client.execute_workflow(
        SimpleAgentWorkflow.run,
        id='my-agent-task',
        task_queue='sample_queue'
    )

    print(result)

asyncio.run(main())
```

## Architecture

The project uses a three-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                            │
│  BaseAgent → CodeActAgent → SimpleAgent                     │
│  (PydanticAI agents with tool definitions)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Workflow Layer                            │
│  CodeActAgentWorkflow + SimpleAgentWorkflow                 │
│  (Temporal workflows for orchestration)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    Sandbox Layer                            │
│  PersistentContainerSandbox (core operations)               │
│  DurablePersistentContainerSandbox (Temporal activities)    │
│  StatelessPersistentSandbox (agent tool adapter)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 Docker Container                            │
│  Python 3.11 + uv + persistent state storage                │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Docker Volume (Persistent Storage)             │
│  workflow-{id} volume at /persistent-storage/               │
│  Stores Python state and files (survives crashes)           │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### Agents (`temporal.pydanticai.codeact.agents`)

- **`BaseAgent`** - Abstract base class with model configuration, MCP toolsets, and Temporal wrapping
- **`CodeActAgent`** - Code execution agent with Docker sandbox tools (blacklists container lifecycle ops)
- **`SimpleAgent`** - Minimal concrete implementation for basic code execution tasks

### Workflows (`temporal.pydanticai.codeact.workflows`)

- **`CodeActAgentWorkflow`** - Mixin providing container lifecycle management (start/stop)
- **`SimpleAgentWorkflow`** - Complete example workflow: start container → run agent → cleanup
- **`SandboxWorkflow`** - Lightweight child workflow for individual sandbox operations

### Docker Sandbox (`temporal.pydanticai.codeact.docker_sandbox`)

- **`PersistentContainerSandbox`** - Core implementation with container management and state persistence
- **`DurablePersistentContainerSandbox`** - Wraps all methods as Temporal activities
- **`StatelessPersistentSandbox`** - Converts activities into PydanticAI agent tools via child workflows

### Workers (`temporal.pydanticai.codeact.workers`)

- **`CodeActWorkerRunner`** - Flexible worker builder for running agents with custom workflows and activities
  - Supports multiple agents with AgentPlugin
  - Automatically includes sandbox activities and utilities
  - Extensible with custom workflows and activities

### Data Models (`temporal.pydanticai.codeact.datamodels`)

- **`sandbox.py`** - All sandbox task types and argument models (15+ operations)
- **`codeact.py`** - `CodeActAgentDeps` for runtime container context
- **`agent_builder.py`** - `AgentBuilder` for configuring agents with prompts and models
- **`prompts.py`** - `AgentPrompts` model for system prompts and instructions

## Project Structure

```
code-act-pydanticai/
├── src/
│   └── temporal/
│       └── pydanticai/
│           └── codeact/                    # Main library package
│               ├── __init__.py             # Package exports
│               │
│               ├── agents/                 # AI agent implementations
│               │   ├── base/
│               │   │   ├── base_agent.py         # Abstract base agent
│               │   │   ├── code_act_agent.py     # Code execution agent
│               │   │   └── default_settings.py   # Temporal activity configs
│               │   └── simple_agent.py           # Basic concrete agent
│               │
│               ├── workflows/              # Temporal workflow definitions
│               │   ├── base/
│               │   │   └── codeact_agent_workflow.py  # Container lifecycle mixin
│               │   ├── simple_agent_workflow.py       # Example agent workflow
│               │   └── sandbox_workflow.py            # Sandbox operation workflow
│               │
│               ├── docker_sandbox/         # Docker execution sandbox
│               │   ├── container_sandbox.py      # 3 sandbox implementations
│               │   └── sandbox/                  # State management scripts
│               │       ├── init_state.py
│               │       ├── load_state.py
│               │       ├── save_state.py
│               │       ├── get_state.py
│               │       ├── list_variables.py
│               │       ├── read_variable.py
│               │       └── clear_state.py
│               │
│               ├── datamodels/             # Pydantic data models
│               │   ├── sandbox.py       # Sandbox task models
│               │   ├── codeact.py       # Agent dependencies
│               │   ├── agent_builder.py # Agent configuration
│               │   └── prompts.py       # Prompt models
│               │
│               ├── activities/             # Temporal activity functions
│               │   └── common.py        # Config loading, prompts, utilities
│               │
│               ├── workers/                # Temporal workers
│               │   └── sandbox_worker.py   # CodeActWorkerRunner
│               │
│               └── api/                    # FastAPI application
│                   └── main.py
│
├── tests/                              # Test suite (mirrors src structure)
│   └── temporal/
│       └── pydanticai/
│           └── codeact/
│               ├── test_activities_common.py
│               ├── test_datamodels_agent_builder.py
│               ├── test_datamodels_codeact.py
│               ├── test_datamodels_prompts.py
│               ├── test_datamodels_sandbox.py
│               └── test_sandbox_container.py
│
├── examples/                           # Usage examples
│   ├── simple_agent_example.py
│   └── agent_with_sandbox_tools.py
│
├── docs/                               # Documentation
│   ├── architecture.md
│   ├── getting-started.md
│   ├── api-reference.md
│   ├── sandbox-operations.md
│   ├── examples.md
│   └── sandbox_workflow_demo.md
│
├── app_conf.yml                        # Temporal and LLM configuration
├── agent_prompts.yml                   # Agent prompts and instructions
├── pyproject.toml                      # Project dependencies
├── CLAUDE.md                           # Claude Code instructions
└── README.md
```

## Running the Project

### 1. Start Temporal Server

```bash
# Install Temporal CLI
brew install temporal  # macOS

# Start local dev server
temporal server start-dev
```

### 2. Create and Start Worker

Create a worker script (e.g., `my_worker.py`):

```python
import asyncio
import os
from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner
from temporal.pydanticai.codeact.activities.common import load_config, get_temporal_client, read_prompts
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent
from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
from temporal.pydanticai.codeact.workflows.simple_agent_workflow import SimpleAgentWorkflow
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

async def main():
    # Load configuration
    config = load_config()
    prompts = read_prompts()

    # Create temporal client
    client = await get_temporal_client(
        config['temporal'],
        plugins=[PydanticAIPlugin()]
    )

    # Build agents
    agent = await SimpleAgent.from_agent_confs(
        agent_builder=AgentBuilder(
            prompts=prompts.agent_prompts,
            model_configs=config['llm']['gemini']
        )
    )

    # Create and run worker
    worker = await CodeActWorkerRunner.from_args(
        temporal_client=client,
        task_queue=os.getenv('TASK_QUEUE', 'sample_queue'),
        agents=[agent],
        workflows=[SimpleAgentWorkflow]
    )

    await worker.run()

if __name__ == '__main__':
    asyncio.run(main())
```

Run the worker:
```bash
python my_worker.py
```

### 3. Execute Workflow

**Option A: Run demo script**
```bash
cd src
python run_sandbox_workflow.py
```

**Option B: Execute SimpleAgentWorkflow**
```python
# See Quick Start section above
```

## Documentation

📚 **Comprehensive documentation is available in the `/docs` folder:**

- **[Architecture Guide](docs/architecture.md)** - System design, components, and patterns
- **[Getting Started](docs/getting-started.md)** - Step-by-step tutorial for beginners
- **[API Reference](docs/api-reference.md)** - Complete API documentation for all modules
- **[Sandbox Operations](docs/sandbox-operations.md)** - Detailed reference for all sandbox operations
- **[Examples](docs/examples.md)** - Practical examples with explanations
- **[Testing Guide](docs/testing.md)** - Comprehensive testing documentation
- **[Sandbox Workflow Demo](docs/sandbox_workflow_demo.md)** - Complete demo walkthrough

## Examples

The `examples/` directory contains practical usage examples:

- **`simple_agent_example.py`** - Basic agent instrumentation patterns
- **`agent_with_sandbox_tools.py`** - Advanced tool configuration

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy src/
```

### Linting

```bash
ruff check .
```

### Auto-fix Linting Issues

```bash
ruff check --fix .
```

## Key Concepts

### Persistent State

The sandbox maintains Python variable state across executions using pickle serialization. Variables are stored in Docker volumes, ensuring they survive container crashes, worker restarts, and even Docker daemon restarts.

```python
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox
from temporal.pydanticai.codeact.datamodels.sandbox import ExecutePythonArgs

sandbox = PersistentContainerSandbox()

# First execution
result = await sandbox.execute_python(
    ExecutePythonArgs(
        container_id=container_id,
        code="x = 42\nprint(x)"
    )
)

# Second execution - x is still available!
result = await sandbox.execute_python(
    ExecutePythonArgs(
        container_id=container_id,
        code="print(x * 2)"  # Outputs: 84
    )
)
```

**For comprehensive documentation on persistence, volume management, multi-host deployments, and troubleshooting, see the [Persistent Storage](#persistent-storage) section.**

### Temporal Workflows

Workflows orchestrate long-running agent tasks with automatic retries:

```python
from temporalio import workflow
from temporal.pydanticai.codeact.workflows.base.codeact_agent_workflow import CodeActAgentWorkflow
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent
from temporal.pydanticai.codeact.datamodels.codeact import CodeActAgentDeps

@workflow.defn
class SimpleAgentWorkflow(CodeActAgentWorkflow):
    @workflow.run
    async def run(self, user_task: str) -> str:
        await self._start_sandbox_container(python_packages=['numpy'])
        try:
            agent = await SimpleAgent.from_agent_confs(builder)
            result = await agent.run(
                user_prompt=user_task,
                deps=CodeActAgentDeps(container_id=self.container_id)
            )
            return result.output
        finally:
            await self._stop_sandbox_container()  # Always cleanup
```

### Agent Tools

Agents automatically receive sandbox operations as tools:

```python
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import StatelessPersistentSandbox

# StatelessPersistentSandbox converts activities to agent tools
sandbox = StatelessPersistentSandbox()
agent = await sandbox.instrument_agent(
    agent,
    blacklist=['start_container', 'stop_container']  # Exclude lifecycle ops
)

# Agent can now call: execute_python, execute_bash, read_file, etc.
```

### MCP Integration

The sandbox provides **native support for Model Context Protocol (MCP)** servers, allowing agents to call MCP tools directly from within sandboxed code execution. This enables powerful combinations like using time APIs, web scrapers, file systems, and other external tools seamlessly in agent-generated code.

#### How It Works

When you execute Python code with MCP servers, the sandbox:
1. Starts MCP servers inside the container
2. Extracts tools from each server
3. Creates synchronous Python function wrappers for async MCP tools
4. Injects these functions into the execution namespace
5. Executes your code with all tools available as regular functions
6. Handles event loop coordination automatically

#### Basic Usage

```python
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox
from temporal.pydanticai.codeact.datamodels.sandbox import StartContainerArgs, ExecutePythonArgs
from pydantic_ai.mcp import MCPServerStdio

sandbox = PersistentContainerSandbox()

# Start container
container_id = await sandbox.start_container(StartContainerArgs())

# Create MCP server(s)
time_server = MCPServerStdio("uvx", ["mcp-server-time"])

# Execute code that calls MCP tools as regular functions!
code = '''
# MCP tools are available as regular Python functions
current_time = get_current_time(timezone="America/New_York")
print(f"New York time: {current_time}")
'''

result = await sandbox.execute_python(
    ExecutePythonArgs(container_id=container_id, code=code),
    mcp_servers=[time_server]
)
```

#### Multiple MCP Servers

You can use multiple MCP servers simultaneously:

```python
from pydantic_ai.mcp import MCPServerStdio

# Create multiple servers
time_server = MCPServerStdio("uvx", ["mcp-server-time"])
fetch_server = MCPServerStdio("uvx", ["mcp-server-fetch"])

code = '''
# Tools from both servers available!
time = get_current_time(timezone="UTC")
content = fetch(url="https://example.com")

print(f"Fetched at {time}")
print(f"Content length: {len(content)}")
'''

result = await sandbox.execute_python(
    ExecutePythonArgs(container_id=container_id, code=code),
    mcp_servers=[time_server, fetch_server]
)
```

#### Architecture

The MCP integration uses a file-based execution approach:

```
┌────────────────────────────────────────────────────────────────┐
│                     execute_python() Call                      │
│    (user code + mcp_servers=[...])                             │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│  1. Serialize MCP server configs to JSON                       │
│  2. Write user code to /tmp/user_code.py in container          │
│  3. Set environment variables:                                 │
│     - USER_CODE_PATH=/tmp/user_code.py                         │
│     - MCP_SERVERS_JSON=[...]                                   │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│            Execute: /app/sandbox/execute_with_mcp.py           │
│                                                                 │
│  1. Read config from environment                               │
│  2. Start all MCP servers                                      │
│  3. Create MCPSandboxExecutor with servers                     │
│  4. Get namespace with tool wrappers                           │
│  5. Execute user code with tools available                     │
│  6. Clean up servers                                           │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│                MCPSandboxExecutor Class                         │
│                                                                 │
│  - Coordinates async MCP tools with sync exec() context        │
│  - Creates synchronous wrappers using                          │
│    asyncio.run_coroutine_threadsafe()                          │
│  - Provides namespace dict with all tools as functions         │
│  - Handles multiple servers and tool name conflicts            │
└─────────────────────────────────────────────────────────────────┘
```

#### Available MCP Servers

The sandbox works with any MCP server that supports stdio transport:

- **`mcp-server-time`** - Time and timezone queries
- **`mcp-server-fetch`** - Web content fetching
- **`mcp-server-filesystem`** - File operations
- **`mcp-server-git`** - Git operations
- **`mcp-server-sqlite`** - SQLite database access
- **Custom servers** - Any stdio-based MCP server

#### Key Components

**In Container (`/app/sandbox/`):**
- **`execute_with_mcp.py`** - Entry point script that reads config, starts servers, and executes code
- **`mcp_executor.py`** - MCPSandboxExecutor class for event loop coordination and tool wrapping

**In Host:**
- **`container_sandbox.py`** - `_serialize_mcp_servers()` converts MCPServerStdio to JSON
- **`execute_python()`** - File-based execution when mcp_servers provided

#### Features

✅ **Automatic Tool Discovery** - All tools from all servers become available functions
✅ **Event Loop Coordination** - Async MCP tools work in sync exec() context
✅ **Multiple Servers** - Use any number of MCP servers simultaneously
✅ **Clean Architecture** - File-based approach avoids complex string generation
✅ **Error Handling** - Proper server lifecycle management with AsyncExitStack
✅ **Name Conflict Detection** - Prevents tool name collisions across servers

#### Limitations

- ⚠️ Only stdio-based MCP servers supported (no HTTP/SSE yet)
- ⚠️ Tool functions return strings (MCP response serialized)
- ⚠️ Tools execute with 30-second timeout
- ⚠️ Container needs network access for `uvx` to install MCP servers

#### Testing

Run the MCP integration test:

```bash
pytest tests/test_mcp_integration.py -v
```

See `tests/test_mcp_integration.py` and `src/example/dupa_test.py` for complete examples.

## Persistent Storage

The sandbox provides **automatic persistent storage** using Docker volumes, ensuring that Python variables and files survive container crashes, worker restarts, and even Docker daemon restarts.

### How It Works

When you start a container with a workflow_id, the system automatically:
1. Creates a Docker volume named `workflow-{workflow_id}` (or reuses existing one)
2. Mounts it at `/persistent-storage/` inside the container
3. Saves Python state to `/persistent-storage/{workflow_id}/state/globals.pkl`
4. Restores state automatically when the workflow restarts with the same ID

### Basic Usage

**Persistence is enabled by default:**

```python
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox
from temporal.pydanticai.codeact.datamodels.sandbox import StartContainerArgs, ExecutePythonArgs

# Persistence enabled by default
sandbox = PersistentContainerSandbox()

# Start container with workflow_id
container_id = await sandbox.start_container(
    StartContainerArgs(container_name="data-pipeline-123")
)

# Execute code - variables are saved automatically
await sandbox.execute_python(ExecutePythonArgs(
    container_id=container_id,
    code="results = {'accuracy': 0.95, 'loss': 0.03}"
))

# If worker crashes here and restarts with same ID...

# State is automatically recovered!
await sandbox.execute_python(ExecutePythonArgs(
    container_id=container_id,
    code="print(results)"  # Still works!
))
```

### Configuration Options

**Via Constructor:**
```python
# Enable/disable persistence
sandbox = PersistentContainerSandbox(enable_persistence=True)

# Use NFS for multi-host deployments
sandbox = PersistentContainerSandbox(
    volume_driver='nfs',
    volume_driver_opts={
        'type': 'nfs',
        'o': 'addr=nfs-server.company.com,rw',
        'device': ':/exports/workflows'
    }
)

# Disable persistence for ephemeral workflows
sandbox = PersistentContainerSandbox(enable_persistence=False)
```

**Via Environment Variables:**
```bash
# .env
ENABLE_PERSISTENCE=true
VOLUME_DRIVER=local  # or 'nfs'
NFS_SERVER=nfs-server.company.com
NFS_PATH=/exports/workflows
```

### Volume Management

**List all workflow volumes:**
```python
volumes = await sandbox.list_workflow_volumes()
for vol in volumes:
    print(f"Workflow: {vol['workflow_id']}, Created: {vol['created']}")
```

**Cleanup completed workflows:**
```python
# When workflow completes and you don't need the data anymore
await sandbox.cleanup_workflow_volume("data-pipeline-123")
```

**Manual cleanup (via Docker CLI):**
```bash
# List workflow volumes
docker volume ls | grep workflow-

# Inspect specific volume
docker volume inspect workflow-data-pipeline-123

# Remove specific volume
docker volume rm workflow-data-pipeline-123

# Remove all workflow volumes (careful!)
docker volume rm $(docker volume ls -q | grep "^workflow-")
```

### Storage Paths

**Inside containers:**
- **State**: `/persistent-storage/{workflow_id}/state/globals.pkl`
- **Output**: `/persistent-storage/{workflow_id}/output/`

**On host:**
- **Local**: Docker-managed (`/var/lib/docker/volumes/workflow-{id}`)
- **NFS**: On NFS server at configured path

### Multi-Host Deployments (NFS)

For production deployments across multiple hosts:

```python
sandbox = PersistentContainerSandbox(
    volume_driver='nfs',
    volume_driver_opts={
        'type': 'nfs',
        'o': 'addr=nfs-server.company.com,rw',
        'device': ':/exports/workflows'
    }
)
# Volumes now accessible from any host in the cluster!
```

### Best Practices

✅ **Do:**
- Use meaningful workflow IDs (`data-pipeline-2024-01-15-batch-001`)
- Clean up completed workflows with `cleanup_workflow_volume()`
- Monitor volume usage with `list_workflow_volumes()`
- Use NFS for multi-host production deployments

❌ **Don't:**
- Reuse workflow IDs (each workflow should have unique ID)
- Delete volumes manually (use `cleanup_workflow_volume()`)
- Disable persistence in production unless workflow is truly ephemeral

### Troubleshooting

**State not persisting?**
```python
# Check if persistence is enabled
print(f"Persistence: {sandbox.enable_persistence}")
```

```bash
# Check if volume was created
docker volume ls | grep workflow-{your-workflow-id}

# Check container has volume mounted
docker inspect {container-id} | grep Mounts -A 10
```

**Volume already exists?**
This is normal! The sandbox reuses existing volumes. For a fresh start:
```python
await sandbox.cleanup_workflow_volume("your-workflow-id")
container_id = await sandbox.start_container(...)
```

### Comparison with Alternatives

| Feature | Docker Volumes | SeaweedFS/Other Distributed FS |
|---------|---------------|-------------------------------|
| Setup | ✅ None (built-in) | ❌ Complex (4+ containers) |
| Complexity | ✅ Simple | ❌ High |
| Single-host | ✅ Yes | ✅ Yes |
| Multi-host | ➕ With NFS | ✅ Native |
| Performance | ✅ Local disk | ⚠️ Network overhead |
| Maintenance | ✅ Low | ⚠️ High |

**Recommendation:** Start with Docker volumes. Upgrade to NFS if you need multi-host. Only consider distributed file systems like SeaweedFS if you need advanced features.

## Environment Variables

- `TASK_QUEUE` - Temporal task queue name (default: `sample_queue`)
- `APP_CONFIG_PATH` - Path to configuration file
- `APP_PROMPTS_PATH` - Path to agent prompts file
- `GEMINI_API_KEY` - Google Gemini API key (or in app_conf.yml)
- `ENABLE_PERSISTENCE` - Enable/disable persistent storage (default: `true`)
- `VOLUME_DRIVER` - Volume driver for persistence (`local` or `nfs`, default: `local`)
- `NFS_SERVER` - NFS server address (when using NFS driver)
- `NFS_PATH` - NFS export path (when using NFS driver)

## Testing

Comprehensive test suite using pytest with async support:

```bash
# Run all tests
pytest

# Run unit tests only (no Docker/Temporal required)
pytest -m unit

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_datamodels_sandbox.py
```

### Test Categories

- **Unit Tests** (`-m unit`) - Fast tests with mocked dependencies
- **Integration Tests** (`-m integration`) - Require Docker and/or Temporal
- **Docker Tests** (`-m docker`) - Require Docker daemon
- **Temporal Tests** (`-m temporal`) - Require Temporal server

See [Testing Guide](docs/testing.md) for comprehensive testing documentation.

## Publishing the Library

### Building the Distribution

The library is configured to package only the `temporal` namespace module. To build distribution packages:

```bash
# Build the package using uv (recommended for this project)
uv build

# Or using standard build tools
pip install build twine
python -m build

# This creates:
# - dist/temporal_pydanticai_codeact-0.1.0-py3-none-any.whl (wheel - this is what gets installed)
# - dist/temporal-pydanticai-codeact-0.1.0.tar.gz (source distribution)
```

**Verify the build:**
```bash
# Check what's in the wheel (what users will install)
unzip -l dist/temporal_pydanticai_codeact-0.1.0-py3-none-any.whl | grep temporal

# You should see only:
# temporal/__init__.py
# temporal/pydanticai/__init__.py
# temporal/pydanticai/codeact/...
```

### What Gets Published

The build process packages **only** the `src/temporal/` directory, which contains:
- `temporal/__init__.py` (namespace package)
- `temporal/pydanticai/__init__.py` (namespace package)
- `temporal/pydanticai/codeact/` (the actual library code)

This means users installing the package get:
```
site-packages/
└── temporal/
    └── pydanticai/
        └── codeact/
            ├── __init__.py
            ├── activities/
            ├── agents/
            ├── datamodels/
            ├── docker_sandbox/
            ├── workflows/
            └── workers/
```

### Publishing to PyPI

```bash
# Check the built package
twine check dist/*

# Upload to Test PyPI first (recommended)
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ temporal-pydanticai-codeact

# If everything works, publish to PyPI
twine upload dist/*
```

### Publishing to Private Registry

For private use or internal projects:

```bash
# Configure your private registry
pip config set global.index-url https://your-registry.com/simple/

# Upload to private registry
twine upload --repository-url https://your-registry.com/legacy/ dist/*
```

### Using in Other Projects

After publishing, users can install and use the library:

**Example Project Structure:**
```
my-agent-project/
├── pyproject.toml
├── requirements.txt
└── main.py
```

**requirements.txt:**
```txt
temporal-pydanticai-codeact>=0.1.0
```

**main.py:**
```python
import asyncio
import os
from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner
from temporal.pydanticai.codeact.activities.common import (
    load_config,
    get_temporal_client,
    read_prompts
)
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent
from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
from temporal.pydanticai.codeact.workflows.simple_agent_workflow import SimpleAgentWorkflow
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

async def main():
    # Load configuration
    config = load_config()  # Looks for app_conf.yml in current directory
    prompts = read_prompts()  # Looks for agent_prompts.yml

    # Connect to Temporal
    client = await get_temporal_client(
        config['temporal'],
        plugins=[PydanticAIPlugin()]
    )

    # Build agent
    agent = await SimpleAgent.from_agent_confs(
        agent_builder=AgentBuilder(
            prompts=prompts.agent_prompts,
            model_configs=config['llm']['gemini']
        )
    )

    # Create and run worker
    worker = await CodeActWorkerRunner.from_args(
        temporal_client=client,
        task_queue=os.getenv('TASK_QUEUE', 'my-queue'),
        agents=[agent],
        workflows=[SimpleAgentWorkflow]
    )

    print("Worker started. Press Ctrl+C to stop.")
    await worker.run()

if __name__ == '__main__':
    asyncio.run(main())
```

**Install and run:**
```bash
# Install dependencies (includes temporal-pydanticai-codeact)
pip install -r requirements.txt

# Run your agent
python main.py
```

## Contributing

Contributions are welcome! Please ensure:

1. Code follows existing patterns and style
2. All tests pass (`pytest`)
3. Unit tests pass without external services (`pytest -m unit`)
4. Type checking passes (`mypy src/`)
5. Linting passes (`ruff check .`)
6. New features include tests, documentation, and examples

## License

MIT

## Acknowledgments

Built with:
- [PydanticAI](https://ai.pydantic.dev/) by Anthropic
- [Temporal](https://temporal.io/)
- [Docker](https://www.docker.com/)
- [uv](https://github.com/astral-sh/uv) package manager
