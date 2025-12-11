"""
Unit tests for sandbox data models.

Tests all Pydantic models in src/datamodels/sandbox.py including task types,
argument models, and discriminated unions.
"""

import pytest
from pydantic import ValidationError

from temporal.pydanticai.codeact.datamodels.sandbox import (
    SandboxTaskTypes,
    SandboxBaseArgs,
    StartContainerArgs,
    ExecutePythonArgs,
    ExecuteBashArgs,
    ReadOperationsArgs,
    WriteFileArgs,
    ReadVariableInStateArgs,
    InstallAdditionalPackagesArgs,
    SandboxInputTask,
)


@pytest.mark.unit
class TestSandboxTaskTypes:
    """Test SandboxTaskTypes enum."""

    def test_all_task_types_exist(self):
        """Test that all expected task types are defined."""
        expected_types = [
            "start_container",
            "stop_container",
            "restart_container",
            "execute_python",
            "execute_bash",
            "get_python_state",
            "list_state_variables",
            "read_state_variable",
            "clear_python_state",
            "install_additional_packages",
            "write_file",
            "read_file",
            "list_files",
            "get_container_info",
            "get_all_containers",
            "cleanup_containers",
        ]

        for task_type in expected_types:
            assert hasattr(SandboxTaskTypes, task_type.upper())

    def test_task_type_values(self):
        """Test that task type values match expected strings."""
        assert SandboxTaskTypes.START_CONTAINER == "start_container"
        assert SandboxTaskTypes.EXECUTE_PYTHON == "execute_python"
        assert SandboxTaskTypes.EXECUTE_BASH == "execute_bash"


@pytest.mark.unit
class TestSandboxBaseArgs:
    """Test SandboxBaseArgs model."""

    def test_valid_creation(self, mock_container_id):
        """Test creating valid SandboxBaseArgs."""
        args = SandboxBaseArgs(container_id=mock_container_id)
        assert args.container_id == mock_container_id

    def test_empty_container_id_fails(self):
        """Test that empty container_id fails validation."""
        with pytest.raises(ValidationError):
            SandboxBaseArgs(container_id="")


@pytest.mark.unit
class TestStartContainerArgs:
    """Test StartContainerArgs model."""

    def test_empty_args(self):
        """Test creating StartContainerArgs with no packages."""
        args = StartContainerArgs()
        assert args.python_packages == []
        assert args.system_packages == []

    def test_with_python_packages(self):
        """Test creating with Python packages."""
        packages = ["numpy", "pandas", "scipy"]
        args = StartContainerArgs(python_packages=packages)
        assert args.python_packages == packages
        assert args.system_packages == []

    def test_with_system_packages(self):
        """Test creating with system packages."""
        packages = ["git", "curl", "vim"]
        args = StartContainerArgs(system_packages=packages)
        assert args.system_packages == packages
        assert args.python_packages == []

    def test_with_both_packages(self):
        """Test creating with both package types."""
        py_packages = ["numpy", "pandas"]
        sys_packages = ["git", "curl"]
        args = StartContainerArgs(
            python_packages=py_packages, system_packages=sys_packages
        )
        assert args.python_packages == py_packages
        assert args.system_packages == sys_packages

    def test_none_packages_converted_to_empty_list(self):
        """Test that None packages are converted to empty lists."""
        args = StartContainerArgs(python_packages=None, system_packages=None)
        assert args.python_packages == []
        assert args.system_packages == []


@pytest.mark.unit
class TestExecutePythonArgs:
    """Test ExecutePythonArgs model."""

    def test_minimal_valid_args(self, mock_container_id, sample_python_code):
        """Test creating with minimal required fields."""
        args = ExecutePythonArgs(container_id=mock_container_id, code=sample_python_code)
        assert args.container_id == mock_container_id
        assert args.code == sample_python_code
        assert args.variables is None
        assert args.persist_state is True  # Default value

    def test_with_variables(self, mock_container_id):
        """Test creating with variable injection."""
        variables = {"x": 42, "y": 10, "data": [1, 2, 3]}
        args = ExecutePythonArgs(
            container_id=mock_container_id, code="print(x + y)", variables=variables
        )
        assert args.variables == variables

    def test_persist_state_false(self, mock_container_id):
        """Test creating with persist_state disabled."""
        args = ExecutePythonArgs(
            container_id=mock_container_id, code="print('test')", persist_state=False
        )
        assert args.persist_state is False

    def test_empty_code_fails(self, mock_container_id):
        """Test that empty code fails validation."""
        with pytest.raises(ValidationError):
            ExecutePythonArgs(container_id=mock_container_id, code="")

    def test_complex_variables(self, mock_container_id):
        """Test with complex nested variables."""
        variables = {
            "config": {"host": "localhost", "port": 8080},
            "items": [{"id": 1, "name": "test"}],
            "count": 42,
        }
        args = ExecutePythonArgs(
            container_id=mock_container_id, code="print(config)", variables=variables
        )
        assert args.variables == variables


@pytest.mark.unit
class TestExecuteBashArgs:
    """Test ExecuteBashArgs model."""

    def test_valid_creation(self, mock_container_id, sample_bash_script):
        """Test creating valid ExecuteBashArgs."""
        args = ExecuteBashArgs(container_id=mock_container_id, script=sample_bash_script)
        assert args.container_id == mock_container_id
        assert args.script == sample_bash_script

    def test_simple_command(self, mock_container_id):
        """Test with simple bash command."""
        args = ExecuteBashArgs(container_id=mock_container_id, script="ls -la /tmp")
        assert args.script == "ls -la /tmp"

    def test_empty_script_fails(self, mock_container_id):
        """Test that empty script fails validation."""
        with pytest.raises(ValidationError):
            ExecuteBashArgs(container_id=mock_container_id, script="")


@pytest.mark.unit
class TestReadOperationsArgs:
    """Test ReadOperationsArgs model."""

    def test_valid_creation(self, mock_container_id):
        """Test creating valid ReadOperationsArgs."""
        args = ReadOperationsArgs(container_id=mock_container_id, path="/tmp/test.txt")
        assert args.container_id == mock_container_id
        assert args.path == "/tmp/test.txt"

    def test_directory_path(self, mock_container_id):
        """Test with directory path."""
        args = ReadOperationsArgs(container_id=mock_container_id, path="/tmp/data/")
        assert args.path == "/tmp/data/"

    def test_empty_path_fails(self, mock_container_id):
        """Test that empty path fails validation."""
        with pytest.raises(ValidationError):
            ReadOperationsArgs(container_id=mock_container_id, path="")


@pytest.mark.unit
class TestWriteFileArgs:
    """Test WriteFileArgs model."""

    def test_valid_creation(self, mock_container_id):
        """Test creating valid WriteFileArgs."""
        content = "Hello, World!"
        args = WriteFileArgs(
            container_id=mock_container_id, path="/tmp/test.txt", content=content
        )
        assert args.container_id == mock_container_id
        assert args.path == "/tmp/test.txt"
        assert args.content == content

    def test_empty_content_allowed(self, mock_container_id):
        """Test that empty content is allowed."""
        args = WriteFileArgs(
            container_id=mock_container_id, path="/tmp/empty.txt", content=""
        )
        assert args.content == ""

    def test_multiline_content(self, mock_container_id):
        """Test with multiline content."""
        content = "Line 1\nLine 2\nLine 3"
        args = WriteFileArgs(
            container_id=mock_container_id, path="/tmp/multi.txt", content=content
        )
        assert args.content == content

    def test_empty_path_fails(self, mock_container_id):
        """Test that empty path fails validation."""
        with pytest.raises(ValidationError):
            WriteFileArgs(container_id=mock_container_id, path="", content="test")


@pytest.mark.unit
class TestReadVariableInStateArgs:
    """Test ReadVariableInStateArgs model."""

    def test_valid_creation(self, mock_container_id):
        """Test creating valid ReadVariableInStateArgs."""
        args = ReadVariableInStateArgs(
            container_id=mock_container_id, variable_name="result"
        )
        assert args.container_id == mock_container_id
        assert args.variable_name == "result"

    def test_complex_variable_name(self, mock_container_id):
        """Test with complex variable names."""
        args = ReadVariableInStateArgs(
            container_id=mock_container_id, variable_name="user_data_dict"
        )
        assert args.variable_name == "user_data_dict"

    def test_empty_variable_name_fails(self, mock_container_id):
        """Test that empty variable_name fails validation."""
        with pytest.raises(ValidationError):
            ReadVariableInStateArgs(container_id=mock_container_id, variable_name="")


@pytest.mark.unit
class TestInstallAdditionalPackagesArgs:
    """Test InstallAdditionalPackagesArgs model."""

    def test_python_packages_only(self, mock_container_id):
        """Test installing only Python packages."""
        packages = ["requests", "beautifulsoup4"]
        args = InstallAdditionalPackagesArgs(
            container_id=mock_container_id, python_packages=packages
        )
        assert args.python_packages == packages
        assert args.system_packages == []

    def test_system_packages_only(self, mock_container_id):
        """Test installing only system packages."""
        packages = ["wget", "curl"]
        args = InstallAdditionalPackagesArgs(
            container_id=mock_container_id, system_packages=packages
        )
        assert args.system_packages == packages
        assert args.python_packages == []

    def test_both_package_types(self, mock_container_id):
        """Test installing both package types."""
        py_pkgs = ["numpy"]
        sys_pkgs = ["git"]
        args = InstallAdditionalPackagesArgs(
            container_id=mock_container_id,
            python_packages=py_pkgs,
            system_packages=sys_pkgs,
        )
        assert args.python_packages == py_pkgs
        assert args.system_packages == sys_pkgs


@pytest.mark.unit
class TestSandboxInputTask:
    """Test SandboxInputTask discriminated union."""

    def test_start_container_task(self):
        """Test creating START_CONTAINER task."""
        task = SandboxInputTask(
            task_name=SandboxTaskTypes.START_CONTAINER,
            task_args=StartContainerArgs(python_packages=["numpy"]),
        )
        assert task.task_name == SandboxTaskTypes.START_CONTAINER
        assert isinstance(task.task_args, StartContainerArgs)
        assert task.task_args.python_packages == ["numpy"]

    def test_execute_python_task(self, mock_container_id):
        """Test creating EXECUTE_PYTHON task."""
        task = SandboxInputTask(
            task_name=SandboxTaskTypes.EXECUTE_PYTHON,
            task_args=ExecutePythonArgs(
                container_id=mock_container_id, code="print('test')"
            ),
        )
        assert task.task_name == SandboxTaskTypes.EXECUTE_PYTHON
        assert isinstance(task.task_args, ExecutePythonArgs)

    def test_execute_bash_task(self, mock_container_id):
        """Test creating EXECUTE_BASH task."""
        task = SandboxInputTask(
            task_name=SandboxTaskTypes.EXECUTE_BASH,
            task_args=ExecuteBashArgs(container_id=mock_container_id, script="ls -la"),
        )
        assert task.task_name == SandboxTaskTypes.EXECUTE_BASH
        assert isinstance(task.task_args, ExecuteBashArgs)

    def test_stop_container_task(self, mock_container_id):
        """Test creating STOP_CONTAINER task."""
        task = SandboxInputTask(
            task_name=SandboxTaskTypes.STOP_CONTAINER,
            task_args=SandboxBaseArgs(container_id=mock_container_id),
        )
        assert task.task_name == SandboxTaskTypes.STOP_CONTAINER
        assert isinstance(task.task_args, SandboxBaseArgs)

    def test_mismatched_task_args_fails(self, mock_container_id):
        """Test that mismatched task_name and task_args fails."""
        # This should fail because EXECUTE_PYTHON requires ExecutePythonArgs,
        # not SandboxBaseArgs
        with pytest.raises(ValidationError):
            SandboxInputTask(
                task_name=SandboxTaskTypes.EXECUTE_PYTHON,
                task_args=SandboxBaseArgs(container_id=mock_container_id),
            )


