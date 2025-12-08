# Sandbox Workflow Demo

This demo showcases the **SandboxWorkflow** with persistent state management across multiple Python script executions.

> **💡 New to Code Act PydanticAI?** Start with the [Getting Started Guide](getting-started.md) for setup instructions.
>
> **📚 Looking for API details?** See the [API Reference](api-reference.md) and [Sandbox Operations](sandbox-operations.md) for complete documentation.

## Overview

The demo demonstrates:

1. **Container Startup** - Starts a Docker container with Python packages
2. **First Python Script** - Sets variables in shared state (user_name, calculation_result, items, metadata)
3. **Second Python Script** - Accesses and uses variables from the first script (demonstrating state persistence)
4. **State Queries** - Lists variables, reads specific variables, gets full state
5. **Cleanup** - Stops and removes the container

## Key Feature: Shared State

The sandbox maintains **persistent state** across Python executions:

```python
# First script execution
user_name = "Alice"
calculation_result = 42 * 2
items = ["apple", "banana", "cherry"]
```

```python
# Second script execution - variables are available!
print(f"user_name from state: {user_name}")  # Works!
print(f"calculation_result from state: {calculation_result}")  # Works!
items.append("date")  # Can modify persisted variables
```

## Prerequisites

1. **Temporal Server** running (see [Temporal setup](#temporal-setup))
2. **Docker** installed and running
3. **Configuration file** (`app_conf.yml`) with Temporal connection details

### Temporal Setup

Start a local Temporal server using the Temporal CLI:

```bash
# Install Temporal CLI
brew install temporal  # macOS
# or download from https://github.com/temporalio/cli

# Start local Temporal server
temporal server start-dev
```

The server will be available at `localhost:7233`.

### Configuration File

Create `app_conf.yml` in the project root:

```yaml
temporal:
  url: localhost:7233
  namespace: default
```

Or set the `APP_CONFIG_PATH` environment variable:

```bash
export APP_CONFIG_PATH=/path/to/your/app_conf.yml
```

## Running the Demo

### Step 1: Start the Worker

In one terminal, start the Temporal worker:

```bash
cd src
python workers/sandbox_worker.py
```

You should see output indicating the worker is running:

```
Worker started, polling on task queue: airflow-spark-kb-agent-queue
```

### Step 2: Run the Workflow

In another terminal, run the demo script:

```bash
cd src
python run_sandbox_workflow.py
```

## Expected Output

```
======================================================================
Sandbox Workflow Demo - Shared State Between Python Scripts
======================================================================

Starting workflow: sandbox-demo-abc123...
Task queue: airflow-spark-kb-agent-queue

✓ Workflow started

📦 Task 1: Starting container...
✓ Container started: 7f3a8b2c1d9e

🐍 Task 2: Executing first Python script (setting variables)...
Output: {
  "success": true,
  "output": "First script executed!\nSet user_name: Alice\n..."
}

🐍 Task 3: Executing second Python script (using shared state)...
Output: {
  "success": true,
  "output": "Second script accessing shared state:\nuser_name from state: Alice\n..."
}

📋 Task 4: Listing all variables in shared state...
State variables: {
  "user_name": "str",
  "calculation_result": "int",
  "items": "list",
  "metadata": "dict",
  "doubled": "int",
  "greeting": "str",
  "final_result": "int"
}

🔍 Task 5: Reading specific variable 'greeting' from state...
Variable 'greeting': {
  "success": true,
  "value": "Hello, Alice!",
  "type": "str"
}

📊 Task 6: Getting full Python state...
Full state: {
  "user_name": "Alice",
  "calculation_result": 84,
  "items": ["apple", "banana", "cherry", "date"],
  ...
}

🛑 Task 7: Stopping container and cleaning up...
✓ Container stopped

⏹️  Stopping workflow...
✓ Workflow completed successfully!

======================================================================
Demo completed!
======================================================================
```

## What's Happening Behind the Scenes

### State Persistence Mechanism

The sandbox uses pickle serialization to persist Python state:

1. **Before execution**: Load previous state from `/tmp/sandbox_state/globals.pkl`
2. **During execution**: Variables are created/modified in the global namespace
3. **After execution**: Save non-private variables back to the pickle file

### State Management Scripts

Located in `src/docker_sandbox/sandbox/`:

- `init_state.py` - Initialize empty state on container start
- `load_state.py` - Load state before script execution
- `save_state.py` - Save state after script execution
- `get_state.py` - Retrieve full state dictionary
- `list_variables.py` - List all variables with types
- `read_variable.py` - Read specific variable value
- `clear_state.py` - Clear all persisted state

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Temporal Workflow                        │
│  (SandboxWorkflow - Long-running, durable execution)       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ signals/queries
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Temporal Activities                            │
│  (PersistentContainerSandbox methods)                      │
│   - start_container                                         │
│   - execute_python                                          │
│   - get_python_state                                        │
│   - etc.                                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Docker API
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Docker Container                               │
│  - Python 3.11 + uv package manager                        │
│  - Persistent state via pickle files                        │
│  - Isolated execution environment                           │
└─────────────────────────────────────────────────────────────┘
```

## Customizing the Demo

You can modify `run_sandbox_workflow.py` to:

- Install different Python packages
- Execute different code snippets
- Test more complex state persistence scenarios
- Add bash commands execution
- Write/read files in the container

Example: Execute NumPy calculations with shared state:

```python
first_script = """
import numpy as np
data = np.array([1, 2, 3, 4, 5])
mean_value = np.mean(data)
print(f"Mean: {mean_value}")
"""

second_script = """
# Access variables from first script
import numpy as np
std_value = np.std(data)  # 'data' is available from first script!
result = {"mean": mean_value, "std": std_value}
print(f"Results: {result}")
"""
```

## Environment Variables

- `TASK_QUEUE` - Temporal task queue name (default: `airflow-spark-kb-agent-queue`)
- `APP_CONFIG_PATH` - Path to configuration file
- `APP_PROMPTS_PATH` - Path to agent prompts file (if using agents)

## Troubleshooting

### Worker Not Connecting

**Problem**: Worker can't connect to Temporal server

**Solution**:
- Ensure Temporal server is running: `temporal server start-dev`
- Check `app_conf.yml` has correct Temporal URL

### Container Build Failures

**Problem**: Docker image fails to build

**Solution**:
- Ensure Docker daemon is running
- Check Dockerfile at `src/docker_sandbox/sandbox/Dockerfile.pythonuv`
- Verify internet connection (for downloading uv)

### State Not Persisting

**Problem**: Variables not available in second script

**Solution**:
- Ensure `persist_state=True` in `ExecutePythonArgs`
- Check that variables don't start with `_` (private variables are excluded)
- Verify variables are not functions or classes (only data is persisted)

## Next Steps

### Learn More

- **[Getting Started](getting-started.md)** - Complete tutorial for beginners
- **[Architecture](architecture.md)** - Understand how components work together
- **[Examples](examples.md)** - More practical usage patterns
- **[Sandbox Operations](sandbox-operations.md)** - Complete operation reference
- **[API Reference](api-reference.md)** - Full API documentation

### Explore the Code

- `SandboxWorkflow` implementation: `src/workflows/sandbox_workflow.py:18-81`
- Activity implementations: `src/docker_sandbox/container_sandbox.py:42-880`
- Data models: `src/datamodels/sandbox.py`
- State management scripts: `src/docker_sandbox/sandbox/*.py`

### Try More Examples

- **Multi-step calculations** with persistent state (see [Examples](examples.md#3-multi-step-calculation-with-state))
- **Data analysis workflows** with pandas and numpy (see [Examples](examples.md#2-data-analysis-agent))
- **Custom agents** extending CodeActAgent (see [Examples](examples.md#5-custom-agent-extension))
