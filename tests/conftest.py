"""
Pytest configuration and shared fixtures for code-act-pydanticai tests.

This module provides common fixtures and configuration used across all tests,
including mock objects for Docker, Temporal, and agent components.
"""

import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from temporalio.testing import WorkflowEnvironment

# Test configuration paths
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

# Add src directory to Python path for imports
sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """
    Provide test configuration.

    Returns:
        Configuration dictionary with test settings.
    """
    return {
        "temporal": {
            "url": "localhost:7233",
            "namespace": "default"
        },
        "llm": {
            "gemini": {
                "api_key": "test_api_key",
                "model_name": "gemini-2.5-pro"
            }
        }
    }


@pytest.fixture(scope="session")
def test_prompts() -> Dict[str, Dict[str, str]]:
    """
    Provide test agent prompts.

    Returns:
        Dictionary of agent prompts for testing.
    """
    return {
        "simple_agent": {
            "system_prompt": "You are a test agent.",
            "instructions": "Container ID: {{ container_id }}\nPackages: {{ python_packages }}"
        },
        "test_agent": {
            "system_prompt": "Test system prompt.",
            "instructions": "Test instructions."
        }
    }


@pytest.fixture
def mock_docker_client():
    """
    Provide mock Docker client.

    Returns:
        Mock Docker client with common container operations.
    """
    client = MagicMock()

    # Mock container
    mock_container = MagicMock()
    mock_container.id = "test_container_123"
    mock_container.short_id = "test_cont"
    mock_container.status = "running"
    mock_container.name = "test_container"
    mock_container.attrs = {
        "State": {"Running": True, "Status": "running"},
        "Config": {"Image": "python:3.11-slim"}
    }

    # Mock exec operations
    mock_exec = MagicMock()
    mock_exec.start.return_value = (0, b"test output")
    mock_container.exec_run.return_value = mock_exec

    # Mock container operations
    mock_container.stop = MagicMock()
    mock_container.remove = MagicMock()
    mock_container.restart = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}

    # Mock client operations
    client.containers.run.return_value = mock_container
    client.containers.get.return_value = mock_container
    client.containers.list.return_value = [mock_container]

    # Mock images
    client.images.build.return_value = (MagicMock(), [])
    client.images.get.return_value = MagicMock()

    return client


@pytest.fixture
def mock_container_id() -> str:
    """
    Provide mock container ID.

    Returns:
        Test container ID string.
    """
    return "test_container_abc123def456"


@pytest.fixture
async def temporal_env() -> AsyncGenerator[WorkflowEnvironment, None]:
    """
    Provide Temporal test environment.

    Yields:
        Temporal workflow test environment.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest.fixture
def mock_temporal_client():
    """
    Provide mock Temporal client.

    Returns:
        Mock Temporal client for testing.
    """
    client = AsyncMock()

    # Mock workflow handle
    mock_handle = AsyncMock()
    mock_handle.result = AsyncMock(return_value="test result")
    mock_handle.signal = AsyncMock()
    mock_handle.query = AsyncMock(return_value={"status": "running"})

    client.start_workflow = AsyncMock(return_value=mock_handle)
    client.execute_workflow = AsyncMock(return_value="test result")
    client.get_workflow_handle = AsyncMock(return_value=mock_handle)

    return client


@pytest.fixture
def sample_python_code() -> str:
    """
    Provide sample Python code for testing.

    Returns:
        Sample Python code string.
    """
    return """
x = 42
y = 10
result = x + y
print(f"Result: {result}")
"""


@pytest.fixture
def sample_bash_script() -> str:
    """
    Provide sample bash script for testing.

    Returns:
        Sample bash script string.
    """
    return """
#!/bin/bash
echo "Testing bash execution"
ls -la /tmp
"""


@pytest.fixture
def sample_python_state() -> Dict[str, Any]:
    """
    Provide sample Python state for testing.

    Returns:
        Dictionary representing Python variable state.
    """
    return {
        "x": 42,
        "y": 10,
        "result": 52,
        "data": [1, 2, 3, 4, 5],
        "metadata": {"type": "test", "version": "1.0"}
    }


@pytest.fixture
def mock_agent():
    """
    Provide mock PydanticAI agent.

    Returns:
        Mock agent for testing.
    """
    agent = AsyncMock()
    agent.run = AsyncMock(return_value=MagicMock(output="test output"))
    agent.name = "test_agent"
    return agent


@pytest.fixture(autouse=True)
def reset_environment():
    """
    Reset environment variables after each test.

    This fixture automatically runs after each test to clean up
    any environment variable changes.
    """
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_jinja_env():
    """
    Provide mock Jinja2 environment.

    Returns:
        Mock Jinja2 environment for template rendering.
    """
    from jinja2 import Environment, BaseLoader

    env = Environment(loader=BaseLoader())
    return env


# Pytest hooks for better output
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "unit: Unit tests that don't require external services"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests that require Docker/Temporal"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take a long time to run"
    )
    config.addinivalue_line(
        "markers", "docker: Tests that require Docker"
    )
    config.addinivalue_line(
        "markers", "temporal: Tests that require Temporal server"
    )
