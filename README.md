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

✨ **Persistent State Execution** - Variables persist across multiple code executions within the same session
🔒 **Sandboxed Security** - All code runs in isolated Docker containers with resource limits
🔄 **Durable Workflows** - Temporal ensures reliable execution with automatic retries and recovery
🎯 **Type-Safe** - Full Pydantic validation for all inputs and outputs
🛠️ **Flexible Tools** - Agents can execute Python, run bash commands, manage files, and query state
📦 **Dynamic Packages** - Install Python and system packages on-demand during execution
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
git clone https://github.com/yourusername/code-act-pydanticai.git
cd code-act-pydanticai

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

The sandbox maintains Python variable state across executions using pickle serialization:

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

## Environment Variables

- `TASK_QUEUE` - Temporal task queue name (default: `sample_queue`)
- `APP_CONFIG_PATH` - Path to configuration file
- `APP_PROMPTS_PATH` - Path to agent prompts file
- `GEMINI_API_KEY` - Google Gemini API key (or in app_conf.yml)

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
