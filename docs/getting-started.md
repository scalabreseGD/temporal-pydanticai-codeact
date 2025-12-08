# Getting Started with Code Act PydanticAI

This guide walks you through setting up and running your first code-executing AI agent.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.13+** installed
- **Docker Desktop** installed and running
- **Google Gemini API key** (get one from [Google AI Studio](https://makersuite.google.com/app/apikey))
- **uv** package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Installation Steps

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/yourusername/code-act-pydanticai.git
cd code-act-pydanticai

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # Unix/macOS
# or
.venv\Scripts\activate  # Windows
```

### 2. Install and Start Temporal

```bash
# Install Temporal CLI (macOS)
brew install temporal

# Or download from https://github.com/temporalio/cli

# Start local Temporal server
temporal server start-dev
```

The server will start on `localhost:7233`. Keep this terminal running.

### 3. Configure the Project

Create `app_conf.yml` in the project root:

```yaml
temporal:
  url: localhost:7233
  namespace: default

llm:
  gemini:
    api_key: YOUR_GEMINI_API_KEY_HERE
    model_name: gemini-2.5-pro
```

Create `agent_prompts.yml`:

```yaml
simple_agent:
  system_prompt: |
    You are a helpful Python coding assistant with access to a sandboxed Docker execution environment.
    You can execute Python code, run bash commands, and manage files safely.

  instructions: |
    You have access to a Docker container (ID: {{ container_id }}) with these pre-installed packages: {{ python_packages }}.

    Use the execute_python tool to:
    - Perform calculations
    - Analyze data
    - Create visualizations
    - Any Python task the user requests

    Variables persist across executions, so you can build on previous results.
```

### 4. Verify Docker

Ensure Docker is running:

```bash
docker ps
# Should show running containers (may be empty, but no errors)
```

## Your First Agent

### Start the Worker

In a new terminal:

```bash
cd src
python workers/sandbox_worker.py
```

You should see:

```
INFO:root:Worker started, polling on task queue: sample_queue
```

### Run a Simple Task

In another terminal, create `test_agent.py`:

```python
import asyncio
from activities.common import load_config, get_temporal_client
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

async def main():
    # Load configuration
    config = load_config()

    # Connect to Temporal
    client = await get_temporal_client(
        config['temporal'],
        plugins=[PydanticAIPlugin()]
    )

    # Execute workflow
    result = await client.execute_workflow(
        'SimpleAgentWorkflow',
        arg='Calculate the factorial of 10 using Python',
        id='test-agent-1',
        task_queue='sample_queue'
    )

    print(f"\nAgent Result:\n{result}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
cd src
python test_agent.py
```

### What Happens

1. **Container Start**: Docker container is created with numpy and pandas
2. **Agent Initialization**: SimpleAgent loads with sandbox tools
3. **Code Execution**: Agent writes Python code and executes it in the container
4. **State Persistence**: Variables are saved for potential follow-up tasks
5. **Cleanup**: Container is stopped and removed
6. **Result**: Agent's final answer is returned

## Understanding the Output

You'll see output like:

```
Starting container...
Started container abc123def456
Agent Result:
The factorial of 10 is 3,628,800.

I calculated this by executing:
```python
import math
result = math.factorial(10)
print(f"Factorial of 10 is {result:,}")
```
```

## Next Steps

### Try More Complex Tasks

```python
# Data analysis task
result = await client.execute_workflow(
    'SimpleAgentWorkflow',
    arg='Generate a random pandas DataFrame with 100 rows and 5 columns, calculate summary statistics, and create a correlation matrix',
    id='data-analysis-1',
    task_queue='sample_queue'
)
```

### Explore State Persistence

See [Sandbox Workflow Demo](sandbox_workflow_demo.md) for examples of persistent state across multiple executions.

### Create Custom Agents

See [Examples](examples.md) for creating your own agents extending `CodeActAgent`.

## Troubleshooting

### Worker Can't Connect to Temporal

**Problem**: `ConnectionError: Failed to connect to Temporal`

**Solution**:
- Ensure Temporal server is running: `temporal server start-dev`
- Check `app_conf.yml` has correct URL: `localhost:7233`
- Check firewall isn't blocking port 7233

### Docker Image Build Fails

**Problem**: `Image build failed: Could not download uv`

**Solution**:
- Check internet connection
- Try pulling Python base image manually: `docker pull python:3.11-slim`
- Check Docker daemon is running: `docker info`

### Gemini API Errors

**Problem**: `Invalid API key` or `Quota exceeded`

**Solution**:
- Verify API key in `app_conf.yml`
- Check quota at [Google AI Studio](https://makersuite.google.com/)
- Ensure API key has Gemini API enabled

### Container Not Cleaning Up

**Problem**: Containers remain after workflow completion

**Solution**:
- Check workflow has `try/finally` block calling `stop_sandbox_container()`
- Manually clean up: `docker ps -a | grep python-uv-sandbox | awk '{print $1}' | xargs docker rm -f`

## Configuration Reference

### app_conf.yml

```yaml
temporal:
  url: localhost:7233      # Temporal server address
  namespace: default       # Temporal namespace

llm:
  gemini:
    api_key: YOUR_KEY      # Google Gemini API key
    model_name: gemini-2.5-pro  # Model to use
    settings:              # Optional model settings
      temperature: 0.7
      max_tokens: 4096
```

### Environment Variables

Set in `.env` file or export:

```bash
export TASK_QUEUE=sample_queue          # Temporal task queue name
export APP_CONFIG_PATH=./app_conf.yml   # Config file location
export APP_PROMPTS_PATH=./agent_prompts.yml  # Prompts file location
export GEMINI_API_KEY=your_key          # Alternative to app_conf.yml
```

## See Also

- [Architecture](architecture.md) - Understand how components work together
- [API Reference](api-reference.md) - Complete API documentation
- [Sandbox Operations](sandbox-operations.md) - All available sandbox operations
- [Examples](examples.md) - More practical examples
