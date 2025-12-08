# Testing Guide

Comprehensive testing guide for Code Act PydanticAI.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Writing Tests](#writing-tests)
- [Fixtures](#fixtures)
- [Mocking](#mocking)
- [Integration Tests](#integration-tests)
- [Best Practices](#best-practices)

---

## Overview

The project uses **pytest** for testing with **pytest-asyncio** for async test support. Tests are organized by component and marked with categories for selective execution.

### Test Framework

- **pytest** (8.0.0+): Main testing framework
- **pytest-asyncio** (0.23.0+): Async test support
- **unittest.mock**: Mocking Docker and Temporal dependencies

### Test Coverage

The test suite covers:
- ✅ Data models (Pydantic validation)
- ✅ Sandbox container operations
- ✅ Activities and configuration loading
- ⚠️ Agent classes (in progress)
- ⚠️ Workflows (integration tests)

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                          # Shared fixtures and configuration
├── pytest.ini                           # Pytest configuration (in root)
├── test_datamodels_sandbox.py          # Sandbox data models
├── test_datamodels_codeact.py          # CodeAct data models
├── test_datamodels_agent_builder.py    # Agent builder models
├── test_datamodels_prompts.py          # Prompts models
├── test_sandbox_container.py           # Container operations
└── test_activities_common.py           # Activities and utilities
```

---

## Running Tests

### Install Test Dependencies

```bash
# Install dev dependencies
uv sync --all-extras

# Or install manually
uv add --dev pytest pytest-asyncio mypy ruff
```

### Run All Tests

```bash
# From project root
pytest

# With verbose output
pytest -v

# With summary
pytest -ra
```

### Run Specific Test Files

```bash
# Single file
pytest tests/test_datamodels_sandbox.py

# Multiple files
pytest tests/test_datamodels_*.py
```

### Run Specific Tests

```bash
# By test name
pytest tests/test_datamodels_sandbox.py::TestStartContainerArgs::test_empty_args

# By pattern
pytest -k "test_valid_creation"
```

### Run by Category

```bash
# Unit tests only (no Docker/Temporal required)
pytest -m unit

# Integration tests (requires Docker and Temporal)
pytest -m integration

# Exclude slow tests
pytest -m "not slow"

# Docker tests only
pytest -m docker

# Temporal tests only
pytest -m temporal
```

### Coverage Reports

```bash
# Install pytest-cov
uv add --dev pytest-cov

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

---

## Test Categories

Tests are marked with pytest markers for selective execution:

### Available Markers

- **`@pytest.mark.unit`** - Unit tests, no external services required
- **`@pytest.mark.integration`** - Integration tests with Docker/Temporal
- **`@pytest.mark.slow`** - Tests that take significant time
- **`@pytest.mark.docker`** - Tests requiring Docker daemon
- **`@pytest.mark.temporal`** - Tests requiring Temporal server

### Marker Usage

```python
import pytest

@pytest.mark.unit
def test_data_model_validation():
    """Fast unit test."""
    pass

@pytest.mark.integration
@pytest.mark.docker
async def test_container_execution():
    """Integration test requiring Docker."""
    pass

@pytest.mark.slow
@pytest.mark.temporal
async def test_workflow_execution():
    """Slow test requiring Temporal."""
    pass
```

---

## Writing Tests

### Test Structure

Follow the **Arrange-Act-Assert** pattern:

```python
@pytest.mark.unit
async def test_execute_python_simple(sandbox, mock_container_id):
    # Arrange: Set up test data
    code = "print('Hello, World!')"
    args = ExecutePythonArgs(container_id=mock_container_id, code=code)

    # Act: Execute the operation
    result = await sandbox.execute_python(args)

    # Assert: Verify the results
    assert result["success"] is True
    assert "Hello, World!" in result["output"]
```

### Test Naming

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test functions: `test_<what_it_tests>`

**Examples:**
```python
# tests/test_datamodels_sandbox.py
class TestExecutePythonArgs:
    def test_minimal_valid_args(self):
        """Test creating with minimal required fields."""
        pass

    def test_with_variables(self):
        """Test creating with variable injection."""
        pass

    def test_empty_code_fails(self):
        """Test that empty code fails validation."""
        pass
```

### Docstrings

Every test should have a docstring explaining what it tests:

```python
def test_start_container_with_python_packages(self):
    """
    Test starting container with Python packages.

    Verifies that:
    - Container is created successfully
    - Python packages are installed
    - Container ID is returned
    """
    pass
```

---

## Fixtures

### Built-in Fixtures

Located in `tests/conftest.py`:

#### Configuration Fixtures

```python
def test_with_config(test_config):
    """test_config provides test configuration dict."""
    assert test_config["temporal"]["url"] == "localhost:7233"

def test_with_prompts(test_prompts):
    """test_prompts provides test agent prompts."""
    assert "simple_agent" in test_prompts
```

#### Mock Fixtures

```python
def test_with_docker(mock_docker_client):
    """mock_docker_client provides mocked Docker client."""
    container = mock_docker_client.containers.run(...)
    assert container.id is not None

def test_with_temporal(mock_temporal_client):
    """mock_temporal_client provides mocked Temporal client."""
    result = await mock_temporal_client.execute_workflow(...)
    assert result is not None

def test_with_container_id(mock_container_id):
    """mock_container_id provides test container ID string."""
    assert len(mock_container_id) > 0
```

#### Data Fixtures

```python
def test_with_python_code(sample_python_code):
    """sample_python_code provides sample Python script."""
    assert "x = 42" in sample_python_code

def test_with_python_state(sample_python_state):
    """sample_python_state provides sample variable state."""
    assert sample_python_state["x"] == 42
```

### Custom Fixtures

Create fixtures in your test files or conftest.py:

```python
@pytest.fixture
def custom_sandbox_args():
    """Provide custom sandbox arguments for tests."""
    return ExecutePythonArgs(
        container_id="test_id",
        code="print('test')",
        variables={"key": "value"}
    )

def test_with_custom_fixture(custom_sandbox_args):
    assert custom_sandbox_args.code == "print('test')"
```

---

## Mocking

### Mocking Docker Operations

```python
from unittest.mock import MagicMock, AsyncMock, patch

def test_container_operations(mock_docker_client):
    """Test using mocked Docker client."""
    # Setup mock behavior
    mock_container = mock_docker_client.containers.get.return_value
    mock_container.exec_run.return_value.exit_code = 0
    mock_container.exec_run.return_value.output = (b"Success\n",)

    # Use mock
    sandbox = PersistentContainerSandbox()
    sandbox.docker_client = mock_docker_client

    # Verify calls
    mock_docker_client.containers.get.assert_called_once()
```

### Mocking Async Functions

```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations with AsyncMock."""
    mock_func = AsyncMock(return_value="test result")

    result = await mock_func()

    assert result == "test result"
    mock_func.assert_called_once()
```

### Patching

```python
@patch("docker.from_env")
def test_with_patch(mock_from_env):
    """Test using patch decorator."""
    mock_client = MagicMock()
    mock_from_env.return_value = mock_client

    # Code that uses docker.from_env
    sandbox = PersistentContainerSandbox()

    mock_from_env.assert_called_once()
```

---

## Integration Tests

### Docker Integration Tests

Requires Docker daemon running:

```python
@pytest.mark.integration
@pytest.mark.docker
async def test_real_container_execution():
    """Test with actual Docker container."""
    sandbox = PersistentContainerSandbox()

    # Start real container
    container_id = await sandbox.start_container(
        StartContainerArgs(python_packages=["numpy"])
    )

    try:
        # Execute code
        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container_id,
                code="import numpy; print(numpy.__version__)"
            )
        )

        assert result["success"] is True
        assert result["exit_code"] == 0
    finally:
        # Cleanup
        await sandbox.stop_container(
            SandboxBaseArgs(container_id=container_id)
        )
```

### Temporal Integration Tests

Requires Temporal server running:

```python
@pytest.mark.integration
@pytest.mark.temporal
async def test_workflow_execution(temporal_env):
    """Test using Temporal test environment."""
    async with Worker(
        temporal_env.client,
        task_queue="test-queue",
        workflows=[SimpleAgentWorkflow],
        activities=sandbox.activities()
    ):
        result = await temporal_env.client.execute_workflow(
            SimpleAgentWorkflow.run,
            "test task",
            id="test-workflow",
            task_queue="test-queue"
        )

        assert result is not None
```

### Running Integration Tests

```bash
# Ensure services are running
docker ps  # Docker daemon
temporal server start-dev  # Temporal server

# Run integration tests
pytest -m integration

# Run only Docker integration tests
pytest -m "integration and docker"

# Run only Temporal integration tests
pytest -m "integration and temporal"
```

---

## Best Practices

### 1. Test Independence

Each test should be independent and not rely on other tests:

```python
# Good: Independent test
@pytest.fixture
def sandbox():
    s = PersistentContainerSandbox()
    yield s
    s.cleanup()  # Cleanup after test

# Bad: Tests depending on execution order
def test_step_1():
    global container_id
    container_id = create_container()

def test_step_2():
    # Depends on test_step_1
    use_container(container_id)
```

### 2. Use Fixtures for Setup/Teardown

```python
@pytest.fixture
async def running_container(sandbox):
    """Provide running container with automatic cleanup."""
    container_id = await sandbox.start_container(StartContainerArgs())
    yield container_id
    await sandbox.stop_container(SandboxBaseArgs(container_id=container_id))

async def test_with_container(running_container):
    # Container is ready to use
    # Cleanup happens automatically
    pass
```

### 3. Test Error Cases

```python
def test_invalid_input_raises_error():
    """Test that invalid input raises ValidationError."""
    with pytest.raises(ValidationError):
        ExecutePythonArgs(container_id="", code="")

async def test_container_not_found():
    """Test error when container doesn't exist."""
    sandbox = PersistentContainerSandbox()

    with pytest.raises(Exception, match="Container not found"):
        await sandbox.stop_container(
            SandboxBaseArgs(container_id="nonexistent")
        )
```

### 4. Parametrize Tests

Test multiple inputs efficiently:

```python
@pytest.mark.parametrize("packages,expected", [
    (["numpy"], ["numpy"]),
    (["pandas", "scipy"], ["pandas", "scipy"]),
    ([], []),
    (None, []),
])
def test_package_handling(packages, expected):
    args = StartContainerArgs(python_packages=packages)
    assert args.python_packages == expected
```

### 5. Clear Test Names

```python
# Good: Clear what is being tested
def test_execute_python_with_syntax_error_returns_error_message()
def test_start_container_with_invalid_packages_raises_exception
def test_persistent_state_maintains_variables_across_executions

# Bad: Unclear test names
def test_1()
def test_error()
def test_container()
```

### 6. Keep Tests Fast

- Use unit tests (with mocks) for most testing
- Reserve integration tests for critical paths
- Mark slow tests with `@pytest.mark.slow`

### 7. Test Documentation

```python
class TestExecutePythonArgs:
    """
    Test suite for ExecutePythonArgs model.

    Tests validation, serialization, and all argument combinations.
    """

    def test_minimal_valid_args(self):
        """Test creating with only required fields."""
        pass

    def test_with_all_optional_args(self):
        """Test creating with all optional fields populated."""
        pass
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Install uv
      run: curl -LsSf https://astral.sh/uv/install.sh | sh

    - name: Install dependencies
      run: uv sync --all-extras

    - name: Run unit tests
      run: pytest -m unit

    - name: Run integration tests
      run: |
        docker pull python:3.11-slim
        pytest -m integration
```

---

## Troubleshooting

### Tests Failing with Docker Errors

**Problem**: `docker.errors.DockerException: Error while fetching server API version`

**Solution**:
- Ensure Docker daemon is running: `docker ps`
- For unit tests, use `pytest -m unit` to skip Docker tests
- Check Docker socket permissions

### Tests Failing with Temporal Errors

**Problem**: `ConnectionError: Failed to connect to Temporal`

**Solution**:
- Ensure Temporal server is running: `temporal server start-dev`
- For unit tests, use `pytest -m unit` to skip Temporal tests
- Check Temporal server health: `temporal workflow list`

### Slow Tests

**Problem**: Tests take too long to run

**Solution**:
```bash
# Run only fast tests
pytest -m "unit and not slow"

# Identify slow tests
pytest --durations=10

# Run in parallel (requires pytest-xdist)
uv add --dev pytest-xdist
pytest -n auto
```

---

## See Also

- [API Reference](api-reference.md) - Complete API documentation
- [Examples](examples.md) - Practical usage patterns
- [Sandbox Operations](sandbox-operations.md) - Sandbox operation reference
- [pytest Documentation](https://docs.pytest.org/) - Official pytest docs
