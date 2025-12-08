"""
Unit tests for CodeAct data models.

Tests CodeActAgentDeps model in src/datamodels/codeact.py.
"""

import pytest
from pydantic import ValidationError

from datamodels.codeact import CodeActAgentDeps


@pytest.mark.unit
class TestCodeActAgentDeps:
    """Test CodeActAgentDeps model."""

    def test_minimal_valid_creation(self, mock_container_id):
        """Test creating with only required container_id."""
        deps = CodeActAgentDeps(container_id=mock_container_id)
        assert deps.container_id == mock_container_id
        assert deps.python_packages is None
        assert deps.system_packages is None

    def test_with_python_packages(self, mock_container_id):
        """Test creating with Python packages."""
        packages = ["numpy", "pandas", "scipy"]
        deps = CodeActAgentDeps(
            container_id=mock_container_id, python_packages=packages
        )
        assert deps.container_id == mock_container_id
        assert deps.python_packages == packages
        assert deps.system_packages is None

    def test_with_system_packages(self, mock_container_id):
        """Test creating with system packages."""
        packages = ["git", "curl"]
        deps = CodeActAgentDeps(
            container_id=mock_container_id, system_packages=packages
        )
        assert deps.container_id == mock_container_id
        assert deps.system_packages == packages
        assert deps.python_packages is None

    def test_with_both_packages(self, mock_container_id):
        """Test creating with both package types."""
        py_packages = ["numpy", "pandas"]
        sys_packages = ["git", "vim"]
        deps = CodeActAgentDeps(
            container_id=mock_container_id,
            python_packages=py_packages,
            system_packages=sys_packages,
        )
        assert deps.container_id == mock_container_id
        assert deps.python_packages == py_packages
        assert deps.system_packages == sys_packages

    def test_empty_container_id_fails(self):
        """Test that empty container_id fails validation."""
        with pytest.raises(ValidationError):
            CodeActAgentDeps(container_id="")

    def test_missing_container_id_fails(self):
        """Test that missing container_id fails validation."""
        with pytest.raises(ValidationError):
            CodeActAgentDeps(python_packages=["numpy"])

    def test_empty_package_lists(self, mock_container_id):
        """Test with empty package lists."""
        deps = CodeActAgentDeps(
            container_id=mock_container_id, python_packages=[], system_packages=[]
        )
        assert deps.python_packages == []
        assert deps.system_packages == []

    def test_model_serialization(self, mock_container_id):
        """Test model can be serialized to dict."""
        deps = CodeActAgentDeps(
            container_id=mock_container_id,
            python_packages=["numpy"],
            system_packages=["git"],
        )
        data = deps.model_dump()
        assert data["container_id"] == mock_container_id
        assert data["python_packages"] == ["numpy"]
        assert data["system_packages"] == ["git"]

    def test_model_deserialization(self, mock_container_id):
        """Test model can be created from dict."""
        data = {
            "container_id": mock_container_id,
            "python_packages": ["pandas"],
            "system_packages": ["curl"],
        }
        deps = CodeActAgentDeps(**data)
        assert deps.container_id == mock_container_id
        assert deps.python_packages == ["pandas"]
        assert deps.system_packages == ["curl"]
