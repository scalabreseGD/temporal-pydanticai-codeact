# Sandbox Operations Reference

Complete guide to all Docker sandbox operations. Refer to source code documentation in `src/docker_sandbox/container_sandbox.py` and `src/datamodels/sandbox.py` for detailed API docs.

## Overview

The sandbox provides 16 operations across 5 categories:

1. **Container Lifecycle** - Start, stop, restart containers
2. **Code Execution** - Run Python and bash code
3. **State Management** - Manage persistent Python variables
4. **File Operations** - Read, write, list files
5. **Container Info** - Query container status

## Operation Categories

### 1. Container Lifecycle

#### start_container

Start new Docker container with package installation.

**Input:** `StartContainerArgs`
- `python_packages`: List[str] - Python packages via uv
- `system_packages`: List[str] - System packages via apt-get

**Returns:** `str` - Container ID

**Example:**
```python
container_id = await sandbox.start_container(
    StartContainerArgs(
        python_packages=["numpy", "pandas", "matplotlib"],
        system_packages=["git", "curl"]
    )
)
```

#### stop_container

Stop and remove container.

**Input:** `SandboxBaseArgs(container_id=...)`

**Returns:** `{"success": True}`

#### restart_container

Restart running container.

**Input:** `SandboxBaseArgs(container_id=...)`

**Returns:** `{"success": True}`

### 2. Code Execution

#### execute_python

Execute Python code with optional variable injection and state persistence.

**Input:** `ExecutePythonArgs`
- `container_id`: str
- `code`: str - Python code to execute
- `variables`: Optional[Dict[str, Any]] - Variables to inject
- `persist_state`: Optional[bool] - Save variables (default: True)

**Returns:**
```python
{
    "success": bool,
    "output": str,  # stdout
    "error": str | None,  # stderr if failed
    "exit_code": int
}
```

**Examples:**

Simple execution:
```python
result = await sandbox.execute_python(
    ExecutePythonArgs(
        container_id=container_id,
        code="print('Hello from sandbox!')"
    )
)
# result["output"] == "Hello from sandbox!\n"
```

With variable injection:
```python
result = await sandbox.execute_python(
    ExecutePythonArgs(
        container_id=container_id,
        code="result = x + y\nprint(f'Sum: {result}')",
        variables={"x": 10, "y": 32}
    )
)
# result["output"] == "Sum: 42\n"
```

Without state persistence (read-only):
```python
result = await sandbox.execute_python(
    ExecutePythonArgs(
        container_id=container_id,
        code="print(existing_variable)",
        persist_state=False  # Don't save changes
    )
)
```

#### execute_bash

Execute bash commands in container.

**Input:** `ExecuteBashArgs`
- `container_id`: str
- `script`: str - Bash commands

**Returns:** Same as execute_python

**Example:**
```python
result = await sandbox.execute_bash(
    ExecuteBashArgs(
        container_id=container_id,
        script="ls -la /app && echo 'Files listed'"
    )
)
```

### 3. State Management

#### get_python_state

Get all persisted variables.

**Input:** `SandboxBaseArgs(container_id=...)`

**Returns:** `Dict[str, Any]` - All variables

**Example:**
```python
state = await sandbox.get_python_state(
    SandboxBaseArgs(container_id=container_id)
)
# state == {"x": 42, "data": [1, 2, 3], ...}
```

#### list_state_variables

List variable names with their types.

**Input:** `SandboxBaseArgs(container_id=...)`

**Returns:** `Dict[str, str]` - Variable name to type mapping

**Example:**
```python
vars = await sandbox.list_state_variables(
    SandboxBaseArgs(container_id=container_id)
)
# vars == {"x": "int", "data": "list", "df": "DataFrame"}
```

#### read_state_variable

Read specific variable from state.

**Input:** `ReadVariableInStateArgs`
- `container_id`: str
- `variable_name`: str

**Returns:**
```python
{
    "success": bool,
    "value": Any,  # The variable's value
    "type": str,  # Type name
    "error": str | None
}
```

**Example:**
```python
result = await sandbox.read_state_variable(
    ReadVariableInStateArgs(
        container_id=container_id,
        variable_name="result"
    )
)
# result == {"success": True, "value": 42, "type": "int"}
```

#### clear_python_state

Clear all persisted variables (reset to empty state).

**Input:** `SandboxBaseArgs(container_id=...)`

**Returns:** `{"success": True, "output": "State cleared"}`

### 4. File Operations

#### write_file

Write file to container.

**Input:** `WriteFileArgs`
- `container_id`: str
- `path`: str - Full file path
- `content`: str - File content

**Returns:** `{"success": bool, "error": str | None}`

**Example:**
```python
result = await sandbox.write_file(
    WriteFileArgs(
        container_id=container_id,
        path="/tmp/data.csv",
        content="name,age\nAlice,30\nBob,25"
    )
)
```

#### read_file

Read file from container.

**Input:** `ReadOperationsArgs`
- `container_id`: str
- `path`: str - File path

**Returns:**
```python
{
    "success": bool,
    "content": str | None,
    "error": str | None
}
```

**Example:**
```python
result = await sandbox.read_file(
    ReadOperationsArgs(
        container_id=container_id,
        path="/tmp/data.csv"
    )
)
# result["content"] contains file contents
```

#### list_files

List directory contents.

**Input:** `ReadOperationsArgs`
- `container_id`: str
- `path`: str - Directory path

**Returns:** Same format as execute_bash (ls -la output)

**Example:**
```python
result = await sandbox.list_files(
    ReadOperationsArgs(
        container_id=container_id,
        path="/tmp"
    )
)
# result["output"] contains ls -la output
```

### 5. Container Info

#### get_container_info

Get information about specific container.

**Input:** `SandboxBaseArgs(container_id=...)`

**Returns:**
```python
{
    "running": bool,
    "id": str,
    "short_id": str,
    "status": str,
    "image": str,
    "name": str
}
```

#### get_all_containers

Get info about all managed containers.

**Returns:** `Dict[str, Dict]` - Container ID to info mapping

#### cleanup_containers

Stop and remove all managed containers.

**Returns:** `{"success": True}`

## Persistent State Details

### How State Works

Variables persist using pickle serialization:

1. **Before execution**: Load `/tmp/sandbox_state/globals.pkl`
2. **During execution**: Variables created/modified
3. **After execution**: Save picklable, non-private variables

### What Gets Persisted

✅ **Saved:**
- Basic types: int, float, str, bool, None
- Collections: list, dict, tuple, set
- NumPy arrays, pandas DataFrames
- Custom objects (if picklable)

❌ **Not Saved:**
- Variables starting with `_`
- Functions and classes
- Modules
- File handles
- Non-picklable objects

### Example Workflow

```python
# Execution 1: Create variables
await sandbox.execute_python(ExecutePythonArgs(
    container_id=cid,
    code="""
import numpy as np
data = np.array([1, 2, 3, 4, 5])
mean = np.mean(data)
print(f"Mean: {mean}")
"""
))

# Execution 2: Use persisted variables
await sandbox.execute_python(ExecutePythonArgs(
    container_id=cid,
    code="""
# 'data' and 'mean' are still available!
std = np.std(data)
result = {"mean": mean, "std": std}
print(f"Stats: {result}")
"""
))

# Query state
state = await sandbox.get_python_state(SandboxBaseArgs(container_id=cid))
# state contains: data, mean, std, result
```

## Best Practices

### 1. Always Use Try/Finally for Cleanup

```python
container_id = await sandbox.start_container(...)
try:
    # Your operations
    result = await sandbox.execute_python(...)
finally:
    await sandbox.stop_container(SandboxBaseArgs(container_id=container_id))
```

### 2. Handle Errors

```python
result = await sandbox.execute_python(ExecutePythonArgs(...))

if not result["success"]:
    print(f"Error: {result['error']}")
    print(f"Exit code: {result['exit_code']}")
else:
    print(f"Output: {result['output']}")
```

### 3. Install Packages at Start

```python
# Good: Install upfront
container_id = await sandbox.start_container(
    StartContainerArgs(python_packages=["pandas", "scikit-learn"])
)

# Also works: Install later if needed
await sandbox.install_additional_packages(
    InstallAdditionalPackagesArgs(
        container_id=container_id,
        python_packages=["matplotlib"]
    )
)
```

### 4. Clear State Between Tasks

```python
# Reset state for new task
await sandbox.clear_python_state(SandboxBaseArgs(container_id=container_id))
```

## See Also

- [API Reference](api-reference.md) - Complete API documentation
- [Architecture](architecture.md) - How state persistence works
- [Examples](examples.md) - Practical usage patterns
- Source: `src/docker_sandbox/container_sandbox.py` - Full implementation
