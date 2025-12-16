# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python library named **temporal.pydanticai.codeact**, a reusable package for building agents with code execution capabilities using:
- **PydanticAI** (v1.27.0) - Anthropic's agent framework for building production-grade GenAI applications
- **Temporal** (v1.19.0) - Workflow orchestration for reliable, long-running processes
- **Docker Python Client** (v7.1.0) - Programmatic Docker container management

The library is structured as a proper Python package under the namespace `temporal.pydanticai.codeact`.

## Environment Setup

- **Python Version**: 3.13+
- **Virtual Environment**: `.venv/` (already configured)
- **Package Manager**: uv (inferred from pyproject.toml structure)

## Core Dependencies

- **pydantic-ai** (>=1.27.0): Agent framework for building type-safe AI applications
- **temporalio** (>=1.19.0): Workflow orchestration and durable execution
- **docker** (>=7.1.0): Docker Engine API client for container management

## Documentation Requirements

**CRITICAL**: Before writing any code that uses external libraries or frameworks, you MUST check Context7 MCP for the most up-to-date documentation. Use the `mcp__context7__resolve-library-id` and `mcp__context7__get-library-docs` tools to retrieve current API references and code examples.

This is especially important for:
- PydanticAI API usage and patterns
- Python standard library updates (since this uses Python 3.13+)
- Any third-party dependencies added to the project

## Common Commands

### Environment Management
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (when added to pyproject.toml)
uv sync

# Add new dependencies
uv add <package-name>
```

### Development Workflow
```bash
# Run all tests
pytest

# Run tests from specific module
pytest tests/temporal/pydanticai/codeact/test_datamodels_codeact.py

# Run with verbose output
pytest -v

# Run only unit tests (no Docker/Temporal required)
pytest -m unit

# Type checking
mypy src/

# Linting
ruff check .

# Auto-fix linting issues
ruff check --fix .
```

## Package Structure

The library is organized under the namespace `temporal.pydanticai.codeact`:

```
src/
└── temporal/
    └── pydanticai/
        └── codeact/
            ├── __init__.py             # Package exports
            ├── activities/             # Temporal activities (config loading, utilities)
            ├── agents/                 # PydanticAI agent implementations
            │   ├── base/
            │   │   ├── base_agent.py         # Abstract base agent
            │   │   ├── code_act_agent.py     # Code execution agent
            │   │   └── default_settings.py   # Temporal activity configs
            │   └── simple_agent.py           # Concrete agent example
            ├── api/                    # FastAPI application
            ├── datamodels/             # Pydantic models for all data structures
            ├── docker_sandbox/         # Docker container sandbox implementations
            ├── workflows/              # Temporal workflow definitions
            └── workers/                # Temporal worker configurations
                └── sandbox_worker.py   # CodeActWorkerRunner class
```

Tests mirror the source structure:
```
tests/
└── temporal/
    └── pydanticai/
        └── codeact/
            ├── test_activities_common.py
            ├── test_datamodels_*.py
            └── test_sandbox_container.py
```

## Import Patterns

Always use fully qualified imports from the `temporal.pydanticai.codeact` namespace:

```python
# Agents
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent
from temporal.pydanticai.codeact.agents.base.code_act_agent import CodeActAgent

# Data models
from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
from temporal.pydanticai.codeact.datamodels.codeact import CodeActAgentDeps
from temporal.pydanticai.codeact.datamodels.sandbox import ExecutePythonArgs

# Workflows
from temporal.pydanticai.codeact.workflows.simple_agent_workflow import SimpleAgentWorkflow

# Activities and utilities
from temporal.pydanticai.codeact.activities.common import load_config, get_temporal_client

# Workers
from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner
```

## Architecture Overview

### Three-Layer Architecture

1. **Agent Layer** - PydanticAI agents with tool definitions
   - `BaseAgent`: Abstract base with model configuration
   - `CodeActAgent`: Code execution agent with sandbox tools
   - `SimpleAgent`: Concrete implementation example

2. **Workflow Layer** - Temporal workflows for orchestration
   - `CodeActAgentWorkflow`: Mixin for container lifecycle management
   - `SimpleAgentWorkflow`: Complete agent workflow example
   - `SandboxWorkflow`: Individual sandbox operation workflow

3. **Sandbox Layer** - Docker container execution
   - `PersistentContainerSandbox`: Core container operations
   - `DurablePersistentContainerSandbox`: Temporal activities wrapper
   - `StatelessPersistentSandbox`: Agent tool adapter

### Key Components

- **Workers**: Use `CodeActWorkerRunner` to create flexible workers that support multiple agents and workflows
- **State Management**: Python variables persist across executions using pickle serialization
- **Tool Instrumentation**: Sandbox operations automatically become agent tools
- **Durable Execution**: Temporal ensures reliability with retries and recovery

## MCP Server Integration

### Overview

The library provides comprehensive Model Context Protocol (MCP) server integration at two levels:

1. **Agent-Level** - MCP servers as tools available to CodeActAgent subclasses
2. **Sandbox-Level** - MCP tools callable from within sandboxed Python code execution

### Agent-Level MCP Integration

**CodeActAgent** automatically integrates MCP servers by:
1. Retrieving server configs from `_get_mcp_toolsets()`
2. Serializing configurations for container execution
3. Extracting tool schemas as Python function signatures
4. Injecting signatures into agent instructions
5. Making tools callable in sandbox executions

**Creating an Agent with MCP Tools:**

```python
from temporal.pydanticai.codeact.agents.base.code_act_agent import CodeActAgent
from pydantic_ai import WrapperToolset
from pydantic_ai.mcp import MCPServerStdio

class DataAnalysisAgent(CodeActAgent):
    """Agent with time and fetch tool access."""
    agent_name = 'data_analysis_agent'

    @staticmethod
    async def _get_mcp_toolsets(**kwargs):
        """Define MCP servers for this agent."""
        return {
            'time': WrapperToolset(MCPServerStdio("uvx", ["mcp-server-time"])),
            'fetch': WrapperToolset(MCPServerStdio("uvx", ["mcp-server-fetch"]))
        }
```

**Configuring Agent Prompts with MCP Tools:**

```yaml
# agent_prompts.yml
data_analysis_agent:
  system_prompt: "You are a data analysis assistant with external tool access."
  instructions: |
    Docker sandbox: {{ container_id }}
    Packages: {{ python_packages }}
    Variables: {{ sandbox_variable_names }}
    Files: {{ sandbox_files }}

    {% if tools_as_func %}
    ## External Tools Available

    The following MCP tools are available as Python functions:

    {% for func in tools_as_func %}
    ```python
    {{ func }}
    ```
    {% endfor %}

    Call these as regular functions in your execute_python code.
    {% endif %}
```

**Key Points:**

- Override `_get_mcp_toolsets()` in your CodeActAgent subclass
- Return dict of `{name: WrapperToolset(MCPServer...)}`
- Use `{{ tools_as_func }}` in instruction templates to show tool signatures
- Tools are automatically available in sandbox Python executions
- Supports `MCPServerStdio`, `MCPServerSSE`, `MCPServerStreamableHTTP`

**What Happens Internally:**

1. `_build_agent()` calls `_get_mcp_toolsets()`
2. Serializes servers with `serialize_mcp_servers()`
3. Extracts signatures via `extract_mcp_tools_as_functions` activity
4. Passes signatures to `instructions()` renderer as `tools_as_func`
5. Provides serialized servers to `instrument_agent()` for runtime use

### Sandbox-Level MCP Integration

You can also use MCP servers directly with the sandbox (without agent-level integration):

```python
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox
from temporal.pydanticai.codeact.datamodels.sandbox import ExecutePythonArgs
from pydantic_ai.mcp import MCPServerStdio

sandbox = PersistentContainerSandbox()
container_id = await sandbox.start_container(...)

# Define MCP servers
time_server = MCPServerStdio("uvx", ["mcp-server-time"])
fetch_server = MCPServerStdio("uvx", ["mcp-server-fetch"])

# Execute code with MCP tools available
code = '''
time = get_current_time(timezone="UTC")
content = fetch(url="https://example.com")
print(f"Fetched at {time}")
'''

result = await sandbox.execute_python(
    ExecutePythonArgs(container_id=container_id, code=code),
    mcp_servers=[time_server, fetch_server]
)
```

### MCP Tool Extraction

The `extract_mcp_tools_as_functions` activity converts MCP tool schemas to Python function signatures:

```python
from temporal.pydanticai.codeact.activities.mcp_functions import extract_mcp_tools_as_functions
from temporal.pydanticai.codeact.datamodels.mcp_tools import serialize_mcp_servers
from pydantic_ai.mcp import MCPServerStdio

# Serialize servers
server = MCPServerStdio("uvx", ["mcp-server-time"])
serialized = serialize_mcp_servers([server])

# Extract as function signatures
signatures = await extract_mcp_tools_as_functions(serialized)

# Result: list of Python function signature strings
# ['def get_current_time(timezone: str | None = None) -> Any:\n    """Get current time."""']
```

### Common MCP Servers

- **mcp-server-time** - Time/timezone queries
- **mcp-server-fetch** - Web content fetching
- **mcp-server-filesystem** - File operations
- **mcp-server-git** - Git operations
- **mcp-server-sqlite** - SQLite database access

### Best Practices

✅ **Do:**
- Define MCP toolsets in `_get_mcp_toolsets()` for agent-level integration
- Use `{{ tools_as_func }}` in prompts to show available tools to agents
- Test MCP servers locally before deploying
- Document what tools each agent has access to

❌ **Don't:**
- Hard-code tool signatures in prompts (use `{{ tools_as_func }}` instead)
- Mix agent-level and sandbox-level MCP for same tools (choose one approach)
- Forget that containers need network access for `uvx` to install MCP servers

## Common Patterns

### Creating a Worker

```python
from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent

worker = await CodeActWorkerRunner.from_args(
    temporal_client=client,
    task_queue='my-queue',
    agents=[agent],
    workflows=[MyWorkflow],
    activities=[my_custom_activity]  # Optional
)
await worker.run()
```

### Building an Agent

```python
from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent

agent = await SimpleAgent.from_agent_confs(
    agent_builder=AgentBuilder(
        prompts=prompts,
        model_configs=model_configs
    )
)
```

## Persistent Storage

The library provides **automatic persistent storage** using Docker volumes. Workflow state survives worker crashes, container restarts, and failures.

### Overview

- **Purpose**: Persist Python variables and files across failures
- **Technology**: Named Docker volumes (one per workflow_id)
- **Isolation**: Each workflow gets its own isolated volume
- **Documentation**: See [Persistent Storage](README.md#persistent-storage) section in README.md for comprehensive guide

### How It Works

When you start a container with a `container_name`, a persistent volume is automatically created:

```python
from temporal.pydanticai.codeact.docker_sandbox import PersistentContainerSandbox

sandbox = PersistentContainerSandbox()  # Persistence enabled by default

container_id = await sandbox.start_container(
    StartContainerArgs(container_name="data-pipeline-123")
)
# Creates volume: workflow-data-pipeline-123
# Mounts at: /persistent-storage/
```

### What Gets Persisted

- **Python State**: All variables saved to `/persistent-storage/{workflow_id}/state/globals.pkl`
- **Output Files**: Files written to `/persistent-storage/{workflow_id}/output/`
- **Survives**: Container crashes, worker restarts, Docker restarts

### Usage Examples

**Automatic Recovery:**
```python
# First run
await sandbox.execute_python(ExecutePythonArgs(
    container_id=container_id,
    code="x = 42; results = train_model()"
))

# Worker crashes here...
# Workflow restarts with same container_name...

# State recovered automatically!
await sandbox.execute_python(ExecutePythonArgs(
    container_id=container_id,
    code="print(x, results)"  # Still works!
))
```

**Ephemeral Workflows:**
```python
# Disable persistence for temporary workflows
sandbox = PersistentContainerSandbox(enable_persistence=False)
```

**Cleanup:**
```python
# Delete volume when workflow completes
await sandbox.cleanup_workflow_volume("data-pipeline-123")
```

**List Volumes:**
```python
# See all workflow volumes
volumes = await sandbox.list_workflow_volumes()
```

### Multi-Host Support (NFS)

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
```

Or via environment:
```bash
VOLUME_DRIVER=nfs
NFS_SERVER=nfs-server.company.com
NFS_PATH=/exports/workflows
```

### Configuration

**Environment Variables (.env):**
```bash
ENABLE_PERSISTENCE=true  # Enable/disable (default: true)
VOLUME_DRIVER=local      # local, nfs, azure-file-volume, etc.
```

**Programmatic:**
```python
# With persistence (default)
sandbox = PersistentContainerSandbox()

# Without persistence
sandbox = PersistentContainerSandbox(enable_persistence=False)

# With NFS
sandbox = PersistentContainerSandbox(
    volume_driver='nfs',
    volume_driver_opts={...}
)
```

### Storage Paths

Inside containers:
- **State**: `/persistent-storage/{workflow_id}/state/globals.pkl`
- **Output**: `/persistent-storage/{workflow_id}/output/`

On host:
- **Local**: Docker-managed (`/var/lib/docker/volumes/workflow-{id}`)
- **NFS**: On NFS server at configured path

### Best Practices

- ✅ Use unique workflow IDs for each execution
- ✅ Clean up volumes when workflows complete
- ✅ Use NFS driver for multi-host deployments
- ✅ Monitor disk usage with `list_workflow_volumes()`
- ❌ Don't reuse workflow IDs across different workflows
- ❌ Don't manually delete volumes (use `cleanup_workflow_volume()`)

### Troubleshooting

**Check if volume exists:**
```bash
docker volume ls | grep workflow-
```

**Inspect volume:**
```bash
docker volume inspect workflow-{workflow-id}
```

**Check mount in container:**
```bash
docker exec {container-id} ls -la /persistent-storage/
```