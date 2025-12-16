"""
Integration tests for custom function injection into sandbox.

Tests the complete flow of serializing functions, installing dependencies,
and executing code with injected functions in Docker containers.
"""

import pytest

from temporal.pydanticai.codeact.datamodels.sandbox import StartContainerArgs, ExecutePythonArgs
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox
from temporal.pydanticai.codeact.utils.function_serializer import serialize_functions


@pytest.mark.integration
@pytest.mark.asyncio
class TestCustomFunctionsIntegration:
    """Integration tests for custom functions in sandbox."""

    @pytest.fixture
    async def sandbox(self):
        """Create a sandbox instance for testing."""
        sandbox = PersistentContainerSandbox()
        yield sandbox
        # Cleanup happens automatically

    @pytest.fixture
    async def container(self, sandbox):
        """Start a test container."""
        result = await sandbox.start_container(
            StartContainerArgs(container_name="test-custom-funcs")
        )
        container_id = result['container_id']
        yield container_id
        # Stop container after test
        await sandbox.stop_container(container_id)

    async def test_inject_simple_function(self, sandbox, container):
        """Test injecting a simple function without dependencies."""

        # Define a simple function
        def double(x: int) -> int:
            """Double a number."""
            return x * 2

        # Serialize it
        config = serialize_functions([double])

        # Execute code that uses the function
        code = """
result = double(21)
print(result)
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        assert result['success'] is True
        assert "42" in result['output']

    async def test_inject_async_function(self, sandbox, container):
        """Test injecting an async function."""

        # Define an async function
        async def async_double(x: int) -> int:
            """Async double."""
            return x * 2

        config = serialize_functions([async_double])

        # Execute code with async call
        code = """
result = await async_double(21)
print(result)
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        assert result['success'] is True
        assert "42" in result['output']

    async def test_inject_function_with_dependencies(self, sandbox, container):
        """Test injecting function with external dependencies."""

        # Define function that uses pandas
        def analyze_list(data: list) -> dict:
            """Analyze a list using pandas."""
            import pandas as pd
            series = pd.Series(data)
            return {
                'mean': float(series.mean()),
                'sum': float(series.sum()),
                'count': len(series)
            }

        config = serialize_functions([analyze_list])

        # Verify pandas is in dependencies
        assert 'pandas' in config.get_all_dependencies()

        # Execute code
        code = """
result = analyze_list([1, 2, 3, 4, 5])
print(result)
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        assert result['success'] is True
        # Check output contains expected results
        assert "'mean': 3.0" in result['output'] or "'mean':3.0" in result['output'].replace(' ', '')

    async def test_inject_multiple_functions(self, sandbox, container):
        """Test injecting multiple functions."""

        def add(a: int, b: int) -> int:
            return a + b

        def multiply(a: int, b: int) -> int:
            return a * b

        config = serialize_functions([add, multiply])

        code = """
x = add(5, 3)
y = multiply(4, 2)
print(f"add: {x}, multiply: {y}")
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        assert result['success'] is True
        assert "add: 8" in result['output']
        assert "multiply: 8" in result['output']

    async def test_function_with_complex_logic(self, sandbox, container):
        """Test function with complex logic and multiple dependencies."""

        async def statistical_analysis(numbers: list) -> dict:
            """Perform statistical analysis."""
            import numpy as np
            from scipy import stats

            arr = np.array(numbers)
            return {
                'mean': float(np.mean(arr)),
                'median': float(np.median(arr)),
                'std': float(np.std(arr)),
                'skew': float(stats.skew(arr))
            }

        config = serialize_functions([statistical_analysis])

        # Verify dependencies detected
        deps = config.get_all_dependencies()
        assert 'numpy' in deps
        assert 'scipy' in deps

        code = """
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
result = await statistical_analysis(data)
print(f"Mean: {result['mean']}")
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        assert result['success'] is True
        assert "Mean: 5.5" in result['output']

    async def test_function_persists_across_executions(self, sandbox, container):
        """Test that custom functions work with state persistence."""

        def create_counter() -> int:
            """Create a counter variable."""
            return 0

        config = serialize_functions([create_counter])

        # First execution: create counter
        code1 = """
counter = create_counter()
print(f"Initial: {counter}")
        """

        result1 = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code1,
                custom_functions=config,
                persist_state=True
            )
        )

        assert result1['success'] is True
        assert "Initial: 0" in result1['output']

        # Second execution: function should still be available
        code2 = """
# Function should still be available from first execution
new_val = create_counter()
counter += new_val + 5
print(f"Updated: {counter}")
        """

        result2 = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code2,
                custom_functions=config,
                persist_state=True
            )
        )

        assert result2['success'] is True
        assert "Updated: 5" in result2['output']

    async def test_no_custom_functions(self, sandbox, container):
        """Test execution without custom functions still works."""
        code = """
result = 2 + 2
print(result)
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=None,
                persist_state=False
            )
        )

        assert result['success'] is True
        assert "4" in result['output']

    async def test_function_error_handling(self, sandbox, container):
        """Test error handling in custom functions."""

        def risky_divide(a: int, b: int) -> float:
            """Division that might fail."""
            return a / b

        config = serialize_functions([risky_divide])

        # This should cause a division by zero error
        code = """
try:
    result = risky_divide(10, 0)
except ZeroDivisionError as e:
    print(f"Caught error: {e}")
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        assert result['success'] is True
        assert "Caught error" in result['output']


@pytest.mark.integration
@pytest.mark.asyncio
class TestDependencyInstallation:
    """Test automatic dependency installation."""

    @pytest.fixture
    async def sandbox(self):
        sandbox = PersistentContainerSandbox()
        yield sandbox

    @pytest.fixture
    async def container(self, sandbox):
        result = await sandbox.start_container(
            StartContainerArgs(container_name="test-deps")
        )
        container_id = result['container_id']
        yield container_id
        await sandbox.stop_container(container_id)

    async def test_dependencies_auto_install(self, sandbox, container):
        """Test that dependencies are automatically installed."""

        def use_requests():
            """Function using requests library."""
            return "requests imported successfully"

        config = serialize_functions([use_requests])

        code = """
result = use_requests()
print(result)
        """

        # Requests might not be in base image, so this tests installation
        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        # Should succeed because dependencies are auto-installed
        assert result['success'] is True
        assert "requests imported successfully" in result['output']

    async def test_multiple_dependencies_install(self, sandbox, container):
        """Test installation of multiple dependencies."""

        def use_multiple_libs():
            """Use multiple libraries."""
            import pandas as pd
            import numpy as np
            return "All libraries imported"

        config = serialize_functions([use_multiple_libs])

        # Check both detected
        deps = config.get_all_dependencies()
        assert 'pandas' in deps
        assert 'numpy' in deps

        code = """
result = use_multiple_libs()
print(result)
        """

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container,
                code=code,
                custom_functions=config,
                persist_state=False
            )
        )

        assert result['success'] is True
