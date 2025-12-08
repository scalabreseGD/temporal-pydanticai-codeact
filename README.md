# Code Act PydanticAI

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)

Building intelligent agents with safe code execution capabilities using PydanticAI, Temporal workflows, and Docker sandboxes.

## Overview

**Code Act PydanticAI** combines three powerful technologies to create AI agents that can write and execute code safely in isolated environments with persistent state:

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

```bash
# Clone the repository
git clone https://github.com/yourusername/code-act-pydanticai.git
cd code-act-pydanticai

# Install dependencies
uv sync
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
from activities.common import load_config, get_temporal_client
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
        'SimpleAgentWorkflow',
        arg='Calculate the mean and standard deviation of [1, 2, 3, 4, 5]',
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

### Agents (`src/agents/`)

- **`BaseAgent`** - Abstract base class with model configuration, MCP toolsets, and Temporal wrapping
- **`CodeActAgent`** - Code execution agent with Docker sandbox tools (blacklists container lifecycle ops)
- **`SimpleAgent`** - Minimal concrete implementation for basic code execution tasks

### Workflows (`src/workflows/`)

- **`CodeActAgentWorkflow`** - Mixin providing container lifecycle management (start/stop)
- **`SimpleAgentWorkflow`** - Complete example workflow: start container → run agent → cleanup
- **`SandboxWorkflow`** - Lightweight child workflow for individual sandbox operations

### Docker Sandbox (`src/docker_sandbox/`)

- **`PersistentContainerSandbox`** - Core implementation with container management and state persistence
- **`DurablePersistentContainerSandbox`** - Wraps all methods as Temporal activities
- **`StatelessPersistentSandbox`** - Converts activities into PydanticAI agent tools via child workflows

### Data Models (`src/datamodels/`)

- **`sandbox.py`** - All sandbox task types and argument models (15+ operations)
- **`codeact.py`** - `CodeActAgentDeps` for runtime container context
- **`agent_builder.py`** - `AgentBuilder` for configuring agents with prompts and models
- **`prompts.py`** - `AgentPrompts` model for system prompts and instructions

## Project Structure

```
code-act-pydanticai/
├── src/
│   ├── agents/              # AI agent implementations
│   │   ├── base/
│   │   │   ├── base_agent.py         # Abstract base agent
│   │   │   ├── code_act_agent.py     # Code execution agent
│   │   │   └── default_settings.py   # Temporal activity configs
│   │   └── simple_agent.py           # Basic concrete agent
│   │
│   ├── workflows/           # Temporal workflow definitions
│   │   ├── base/
│   │   │   └── codeact_agent_workflow.py  # Container lifecycle mixin
│   │   ├── simple_agent_workflow.py       # Example agent workflow
│   │   └── sandbox_workflow.py            # Sandbox operation workflow
│   │
│   ├── docker_sandbox/      # Docker execution sandbox
│   │   ├── container_sandbox.py      # 3 sandbox implementations
│   │   └── sandbox/                  # State management scripts
│   │       ├── init_state.py
│   │       ├── load_state.py
│   │       ├── save_state.py
│   │       ├── get_state.py
│   │       ├── list_variables.py
│   │       ├── read_variable.py
│   │       └── clear_state.py
│   │
│   ├── datamodels/          # Pydantic data models
│   │   ├── sandbox.py       # Sandbox task models
│   │   ├── codeact.py       # Agent dependencies
│   │   ├── agent_builder.py # Agent configuration
│   │   └── prompts.py       # Prompt models
│   │
│   ├── activities/          # Temporal activity functions
│   │   └── common.py        # Config loading, prompts, utilities
│   │
│   ├── workers/             # Temporal workers
│   │   └── sandbox_worker.py
│   │
│   └── run_sandbox_workflow.py  # Demo runner script
│
├── examples/                # Usage examples
│   ├── simple_agent_example.py
│   └── agent_with_sandbox_tools.py
│
├── docs/                    # Documentation
│   ├── architecture.md
│   ├── getting-started.md
│   ├── api-reference.md
│   ├── sandbox-operations.md
│   ├── examples.md
│   └── sandbox_workflow_demo.md
│
├── tests/                   # Test suite
├── app_conf.yml             # Temporal and LLM configuration
├── agent_prompts.yml        # Agent prompts and instructions
├── pyproject.toml           # Project dependencies
├── CLAUDE.md                # Claude Code instructions
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

### 2. Start Worker

```bash
cd src
python workers/sandbox_worker.py
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
@workflow.defn
class SimpleAgentWorkflow(CodeActAgentWorkflow):
    @workflow.run
    async def run(self, user_task: str) -> str:
        await self.start_sandbox_container(python_packages=['numpy'])
        try:
            agent = await SimpleAgent.from_agent_confs(builder)
            result = await agent.run(
                user_prompt=user_task,
                deps=CodeActAgentDeps(container_id=self.container_id)
            )
            return result.output
        finally:
            await self.stop_sandbox_container()  # Always cleanup
```

### Agent Tools

Agents automatically receive sandbox operations as tools:

```python
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

## Contributing

Contributions are welcome! Please ensure:

1. Code follows existing patterns and style
2. All tests pass (`pytest`)
3. Unit tests pass without external services (`pytest -m unit`)
4. Type checking passes (`mypy src/`)
5. Linting passes (`ruff check .`)
6. New features include tests, documentation, and examples

## License

TBD

## Acknowledgments

Built with:
- [PydanticAI](https://ai.pydantic.dev/) by Anthropic
- [Temporal](https://temporal.io/)
- [Docker](https://www.docker.com/)
- [uv](https://github.com/astral-sh/uv) package manager
