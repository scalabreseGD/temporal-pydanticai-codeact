"""
Unit tests for Docker sandbox container operations.

Tests PersistentContainerSandbox class in src/docker_sandbox/container_sandbox.py.
Uses mocks to avoid requiring actual Docker daemon.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox
from temporal.pydanticai.codeact.datamodels.sandbox import (
    StartContainerArgs,
    ExecutePythonArgs,
    ExecuteBashArgs,
    SandboxBaseArgs,
    ReadOperationsArgs,
    WriteFileArgs,
    ReadVariableInStateArgs,
    InstallAdditionalPackagesArgs,
)


@pytest.mark.unit
class TestPersistentContainerSandbox:
    """Test PersistentContainerSandbox class."""

    @pytest.fixture
    def sandbox(self, mock_docker_client):
        """Create sandbox instance with mock Docker client."""
        with patch("docker.from_env", return_value=mock_docker_client):
            sandbox = PersistentContainerSandbox()
            sandbox.docker_client = mock_docker_client
            return sandbox

    @pytest.mark.asyncio
    async def test_start_container_minimal(self, sandbox, mock_docker_client):
        """Test starting container with no packages."""
        args = StartContainerArgs()

        container_id = await sandbox.start_container(args)

        assert container_id is not None
        assert len(container_id) > 0
        mock_docker_client.containers.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_container_with_python_packages(
        self, sandbox, mock_docker_client
    ):
        """Test starting container with Python packages."""
        args = StartContainerArgs(python_packages=["numpy", "pandas"])

        container_id = await sandbox.start_container(args)

        assert container_id is not None
        mock_docker_client.containers.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_container_with_system_packages(
        self, sandbox, mock_docker_client
    ):
        """Test starting container with system packages."""
        args = StartContainerArgs(system_packages=["git", "curl"])

        container_id = await sandbox.start_container(args)

        assert container_id is not None
        mock_docker_client.containers.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_container(self, sandbox, mock_docker_client, mock_container_id):
        """Test stopping container."""
        # Add container to active containers
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        args = SandboxBaseArgs(container_id=mock_container_id)
        result = await sandbox.stop_container(args)

        assert result["success"] is True
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()
        assert mock_container_id not in sandbox.active_containers

    @pytest.mark.asyncio
    async def test_restart_container(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test restarting container."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        args = SandboxBaseArgs(container_id=mock_container_id)
        result = await sandbox.restart_container(args)

        assert result["success"] is True
        mock_container.restart.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_python_simple(
        self, sandbox, mock_docker_client, mock_container_id, sample_python_code
    ):
        """Test executing simple Python code."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        # Mock successful execution
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"Result: 52\n",)
        mock_container.exec_run.return_value = mock_exec_result

        args = ExecutePythonArgs(container_id=mock_container_id, code=sample_python_code)
        result = await sandbox.execute_python(args)

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "Result: 52" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_python_with_error(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test executing Python code that produces error."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        # Mock failed execution
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 1
        mock_exec_result.output = (b"", b"NameError: name 'undefined_var' is not defined\n")
        mock_container.exec_run.return_value = mock_exec_result

        args = ExecutePythonArgs(
            container_id=mock_container_id, code="print(undefined_var)"
        )
        result = await sandbox.execute_python(args)

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "NameError" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_python_with_variables(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test executing Python with variable injection."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"Sum: 52\n",)
        mock_container.exec_run.return_value = mock_exec_result

        variables = {"x": 42, "y": 10}
        args = ExecutePythonArgs(
            container_id=mock_container_id,
            code="result = x + y\nprint(f'Sum: {result}')",
            variables=variables,
        )
        result = await sandbox.execute_python(args)

        assert result["success"] is True
        assert "Sum: 52" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_python_persist_state_false(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test executing Python without state persistence."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"42\n",)
        mock_container.exec_run.return_value = mock_exec_result

        args = ExecutePythonArgs(
            container_id=mock_container_id,
            code="print(existing_var)",
            persist_state=False,
        )
        result = await sandbox.execute_python(args)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_bash_simple(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test executing simple bash command."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"total 0\ndrwxr-xr-x 2 root root 40 Jan 1 00:00 .\n",)
        mock_container.exec_run.return_value = mock_exec_result

        args = ExecuteBashArgs(container_id=mock_container_id, script="ls -la /tmp")
        result = await sandbox.execute_bash(args)

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "total" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_bash_with_error(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test executing bash command that fails."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 127
        mock_exec_result.output = (b"", b"bash: nonexistentcommand: command not found\n")
        mock_container.exec_run.return_value = mock_exec_result

        args = ExecuteBashArgs(
            container_id=mock_container_id, script="nonexistentcommand"
        )
        result = await sandbox.execute_bash(args)

        assert result["success"] is False
        assert result["exit_code"] == 127
        assert "command not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_python_state(
        self, sandbox, mock_docker_client, mock_container_id, sample_python_state
    ):
        """Test getting Python state."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        # Mock state retrieval
        import pickle
        state_bytes = pickle.dumps(sample_python_state)
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (state_bytes,)
        mock_container.exec_run.return_value = mock_exec_result

        args = SandboxBaseArgs(container_id=mock_container_id)
        result = await sandbox.get_python_state(args)

        assert isinstance(result, dict)
        # In real implementation, would contain state variables

    @pytest.mark.asyncio
    async def test_list_state_variables(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test listing state variables."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        # Mock variable listing
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b'{"x": "int", "data": "list", "result": "int"}\n',)
        mock_container.exec_run.return_value = mock_exec_result

        args = SandboxBaseArgs(container_id=mock_container_id)
        result = await sandbox.list_state_variables(args)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_read_state_variable(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test reading specific state variable."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        # Mock variable read
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (
            b'{"success": true, "value": 42, "type": "int"}\n',
        )
        mock_container.exec_run.return_value = mock_exec_result

        args = ReadVariableInStateArgs(
            container_id=mock_container_id, variable_name="result"
        )
        result = await sandbox.read_state_variable(args)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_clear_python_state(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test clearing Python state."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"State cleared\n",)
        mock_container.exec_run.return_value = mock_exec_result

        args = SandboxBaseArgs(container_id=mock_container_id)
        result = await sandbox.clear_python_state(args)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_write_file(self, sandbox, mock_docker_client, mock_container_id):
        """Test writing file to container."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"",)
        mock_container.exec_run.return_value = mock_exec_result

        args = WriteFileArgs(
            container_id=mock_container_id,
            path="/tmp/test.txt",
            content="Hello, World!",
        )
        result = await sandbox.write_file(args)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_read_file(self, sandbox, mock_docker_client, mock_container_id):
        """Test reading file from container."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"File content here\n",)
        mock_container.exec_run.return_value = mock_exec_result

        args = ReadOperationsArgs(
            container_id=mock_container_id, path="/tmp/test.txt"
        )
        result = await sandbox.read_file(args)

        assert result["success"] is True
        assert "content" in result

    @pytest.mark.asyncio
    async def test_list_files(self, sandbox, mock_docker_client, mock_container_id):
        """Test listing files in container directory."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (
            b"total 4\n-rw-r--r-- 1 root root 13 Jan 1 00:00 test.txt\n",
        )
        mock_container.exec_run.return_value = mock_exec_result

        args = ReadOperationsArgs(container_id=mock_container_id, path="/tmp")
        result = await sandbox.list_files(args)

        assert result["success"] is True
        assert "output" in result

    @pytest.mark.asyncio
    async def test_get_container_info(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test getting container information."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        args = SandboxBaseArgs(container_id=mock_container_id)
        result = await sandbox.get_container_info(args)

        assert isinstance(result, dict)
        assert "running" in result or "id" in result

    @pytest.mark.asyncio
    async def test_get_all_containers(self, sandbox, mock_docker_client):
        """Test getting all container information."""
        # Add some containers
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers["container1"] = mock_container
        sandbox.active_containers["container2"] = mock_container

        result = await sandbox.get_all_containers()

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_cleanup_containers(self, sandbox, mock_docker_client):
        """Test cleaning up all containers."""
        # Add some containers
        mock_container1 = MagicMock()
        mock_container2 = MagicMock()
        sandbox.active_containers["container1"] = mock_container1
        sandbox.active_containers["container2"] = mock_container2

        result = await sandbox.cleanup_containers()

        assert result["success"] is True
        assert len(sandbox.active_containers) == 0
        mock_container1.stop.assert_called_once()
        mock_container2.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_additional_packages(
        self, sandbox, mock_docker_client, mock_container_id
    ):
        """Test installing additional packages."""
        mock_container = mock_docker_client.containers.get.return_value
        sandbox.active_containers[mock_container_id] = mock_container

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"Successfully installed packages\n",)
        mock_container.exec_run.return_value = mock_exec_result

        args = InstallAdditionalPackagesArgs(
            container_id=mock_container_id,
            python_packages=["requests"],
            system_packages=["curl"],
        )
        result = await sandbox.install_additional_packages(args)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_container_not_found_error(self, sandbox, mock_container_id):
        """Test error handling when container not found."""
        # Don't add container to active_containers
        args = SandboxBaseArgs(container_id=mock_container_id)

        with pytest.raises(Exception):
            await sandbox.stop_container(args)

    @pytest.mark.asyncio
    async def test_start_container_with_custom_name(self, sandbox, mock_docker_client):
        """Test starting container with a custom name (e.g., workflow_id)."""
        custom_name = "test-workflow-12345"

        # Mock exec_run to return proper format for package installation
        mock_container = mock_docker_client.containers.get.return_value
        mock_container.exec_run.return_value = (0, (b"", b""))

        args = StartContainerArgs(
            python_packages=["numpy"],
            container_name=custom_name
        )

        container_id = await sandbox.start_container(args)

        # Should return the custom name instead of Docker's auto-generated ID
        assert container_id == custom_name

        # Verify containers.run was called with the name parameter
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('name') == custom_name
