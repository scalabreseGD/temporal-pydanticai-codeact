"""
Tests for function serialization utilities.

Tests the AST-based dependency extraction, function source extraction,
and complete serialization workflow.
"""

import pytest

from temporal.pydanticai.codeact.datamodels.custom_functions import SerializedFunction, CustomFunctionsConfig
from temporal.pydanticai.codeact.utils.function_serializer import (
    extract_function_source,
    parse_dependencies,
    extract_function_signature,
    extract_function_docstring,
    is_async_function,
    serialize_function,
    serialize_functions,
    generate_injection_script
)


class TestDependencyExtraction:
    """Test AST-based dependency extraction."""

    def test_simple_import(self):
        """Test extraction of simple import statements."""
        code = "import pandas"
        deps = parse_dependencies(code)
        assert "pandas" in deps

    def test_import_with_alias(self):
        """Test import with alias."""
        code = "import pandas as pd"
        deps = parse_dependencies(code)
        assert "pandas" in deps

    def test_multiple_imports(self):
        """Test multiple imports in one statement."""
        code = "import pandas, numpy, matplotlib"
        deps = parse_dependencies(code)
        assert "pandas" in deps
        assert "numpy" in deps
        assert "matplotlib" in deps

    def test_from_import(self):
        """Test from...import statements."""
        code = "from pandas import DataFrame"
        deps = parse_dependencies(code)
        assert "pandas" in deps

    def test_from_import_submodule(self):
        """Test from...import with submodules."""
        code = "from pandas.core.frame import DataFrame"
        deps = parse_dependencies(code)
        assert "pandas" in deps
        assert "core" not in deps  # Should only get top-level package

    def test_mixed_imports(self):
        """Test mix of import styles."""
        code = """
import pandas as pd
from numpy import array
import matplotlib.pyplot as plt
from scipy import stats
        """
        deps = parse_dependencies(code)
        assert "pandas" in deps
        assert "numpy" in deps
        assert "matplotlib" in deps
        assert "scipy" in deps

    def test_stdlib_filtering(self):
        """Test that stdlib modules are filtered out."""
        code = """
import os
import sys
import pandas
import json
        """
        deps = parse_dependencies(code)
        assert "os" not in deps
        assert "sys" not in deps
        assert "json" not in deps
        assert "pandas" in deps

    def test_function_with_imports(self):
        """Test extracting dependencies from function definition."""
        code = """
def analyze_data(df_json):
    import pandas as pd
    import numpy as np
    df = pd.read_json(df_json)
    return df.mean().to_dict()
        """
        deps = parse_dependencies(code)
        assert "pandas" in deps
        assert "numpy" in deps

    def test_indented_function_source(self):
        """Test parsing indented source code (from class methods)."""
        # Simulate source extracted from a class method (with indentation)
        code = """    @staticmethod
    async def search_function(query: str) -> list:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        return ddgs.text(query)
        """
        deps = parse_dependencies(code)
        assert "duckduckgo_search" in deps

    def test_async_function_with_imports(self):
        """Test extracting dependencies from async function."""
        code = """
async def analyze_data(df_json):
    import pandas as pd
    df = pd.read_json(df_json)
    return df.mean().to_dict()
        """
        deps = parse_dependencies(code)
        assert "pandas" in deps


class TestFunctionSourceExtraction:
    """Test function source code extraction."""

    def test_extract_simple_function(self):
        """Test extracting source of a simple function."""

        def sample_func():
            return 42

        source = extract_function_source(sample_func)
        assert "def sample_func():" in source
        assert "return 42" in source

    def test_extract_async_function(self):
        """Test extracting source of async function."""

        async def sample_async():
            return "hello"

        source = extract_function_source(sample_async)
        assert "async def sample_async():" in source
        assert "return" in source

    def test_extract_function_with_params(self):
        """Test extracting function with parameters."""

        def add(a: int, b: int) -> int:
            return a + b

        source = extract_function_source(add)
        assert "def add(a: int, b: int) -> int:" in source
        assert "return a + b" in source

    def test_extract_fails_on_builtin(self):
        """Test that extracting builtin functions fails gracefully."""
        with pytest.raises(ValueError):
            extract_function_source(len)


class TestFunctionMetadata:
    """Test function metadata extraction."""

    def test_extract_signature_sync(self):
        """Test extracting signature from sync function."""

        def sample(x: int, y: str = "default") -> bool:
            return True

        sig = extract_function_signature(sample)
        assert "def sample" in sig
        assert "(x: int, y: str = 'default') -> bool" in sig

    def test_extract_signature_async(self):
        """Test extracting signature from async function - should be sync."""

        async def sample(x: int) -> str:
            """Test docstring."""
            return str(x)

        sig = extract_function_signature(sample)
        # Signature should be SYNC (async functions get sync wrappers)
        assert "def sample" in sig
        assert "async def" not in sig
        assert "(x: int) -> str" in sig
        # Should include docstring
        assert "Test docstring" in sig

    def test_extract_docstring(self):
        """Test extracting docstring."""

        def sample():
            """This is a docstring."""
            return True

        doc = extract_function_docstring(sample)
        assert doc == "This is a docstring."

    def test_extract_docstring_none(self):
        """Test extracting when no docstring exists."""

        def sample():
            return True

        doc = extract_function_docstring(sample)
        assert doc is None

    def test_is_async_true(self):
        """Test detecting async functions."""

        async def sample():
            return True

        assert is_async_function(sample) is True

    def test_is_async_false(self):
        """Test detecting sync functions."""

        def sample():
            return True

        assert is_async_function(sample) is False


class TestSerializeFunction:
    """Test complete function serialization."""

    def test_serialize_simple_function(self):
        """Test serializing a simple function."""

        def helper(x: int) -> int:
            """Helper function."""
            return x * 2

        serialized = serialize_function(helper)

        assert isinstance(serialized, SerializedFunction)
        assert serialized.name == "helper"
        assert "def helper" in serialized.source_code
        assert "return x * 2" in serialized.source_code
        assert serialized.is_async is False
        assert "def helper(x: int) -> int:" in serialized.signature
        assert serialized.docstring == "Helper function."

    def test_serialize_staticmethod(self):
        """Test serializing a static method from a class."""

        class TestClass:
            @staticmethod
            def static_helper(x: int) -> int:
                """Static helper."""
                return x * 3

        serialized = serialize_function(TestClass.static_helper)

        assert serialized.name == "static_helper"
        assert "requests" in serialized.dependencies
        assert serialized.is_async is False

    def test_serialize_async_function(self):
        """Test serializing async function - should generate sync wrapper."""

        async def async_helper(data: str) -> dict:
            """Async helper."""
            import pandas as pd
            df = pd.read_json(data)
            return df.to_dict()

        serialized = serialize_function(async_helper)

        assert serialized.name == "async_helper"
        assert serialized.is_async is True  # Original was async
        assert "pandas" in serialized.dependencies
        assert "nest_asyncio" in serialized.dependencies  # Added for wrapper
        # Signature should be SYNC (no async keyword)
        assert "def async_helper" in serialized.signature
        assert "async def" not in serialized.signature
        # Source should contain both async version and sync wrapper
        assert "__async_async_helper" in serialized.source_code  # Renamed async version
        assert "def async_helper" in serialized.source_code  # Sync wrapper
        assert "asyncio.run" in serialized.source_code  # Wrapper uses asyncio.run

    def test_serialize_function_with_multiple_deps(self):
        """Test serializing function with multiple dependencies."""

        def analyze(data):
            import pandas as pd
            import numpy as np
            from scipy import stats
            # Do something with the imports
            return None

        serialized = serialize_function(analyze)

        assert "pandas" in serialized.dependencies
        assert "numpy" in serialized.dependencies
        assert "scipy" in serialized.dependencies

    def test_signature_includes_docstring(self):
        """Test that signatures include docstrings."""

        def documented_func(x: int, y: str = "default") -> bool:
            """
            This is a test function.

            Args:
                x: An integer parameter
                y: A string parameter

            Returns:
                A boolean value
            """
            return True

        serialized = serialize_function(documented_func)

        # Signature should include the full docstring
        assert "def documented_func" in serialized.signature
        assert "This is a test function" in serialized.signature
        assert "Args:" in serialized.signature
        assert "Returns:" in serialized.signature


class TestSerializeFunctions:
    """Test serializing multiple functions."""

    def test_serialize_multiple_functions(self):
        """Test serializing a list of functions."""

        def func1():
            return 1

        def func2():
            return 2

        config = serialize_functions([func1, func2])

        assert isinstance(config, CustomFunctionsConfig)
        assert len(config.functions) == 2
        assert config.functions[0].name == "func1"
        assert config.functions[1].name == "func2"

    def test_get_all_dependencies(self):
        """Test getting all unique dependencies."""

        def func1():
            import pandas
            return None

        def func2():
            import numpy
            import pandas
            return None

        config = serialize_functions([func1, func2])
        deps = config.get_all_dependencies()

        assert "pandas" in deps
        assert "numpy" in deps
        assert len(deps) == 2  # Should be deduplicated

    def test_get_function_by_name(self):
        """Test retrieving function by name."""

        def target_func():
            return "found"

        def other_func():
            return "other"

        config = serialize_functions([target_func, other_func])
        found = config.get_function_by_name("target_func")

        assert found is not None
        assert found.name == "target_func"

    def test_get_function_by_name_not_found(self):
        """Test retrieving non-existent function."""

        def func1():
            return 1

        config = serialize_functions([func1])
        found = config.get_function_by_name("nonexistent")

        assert found is None


class TestGenerateInjectionScript:
    """Test injection script generation."""

    def test_generate_injection_script(self):
        """Test generating injection script from config."""

        def helper1():
            """First helper."""
            return 1

        def helper2():
            """Second helper."""
            return 2

        config = serialize_functions([helper1, helper2])
        script = generate_injection_script(config)

        assert "# Custom functions injected" in script
        assert "def helper1" in script
        assert "def helper2" in script
        assert "return 1" in script
        assert "return 2" in script

    def test_injection_script_format(self):
        """Test that injection script has proper formatting."""

        def sample():
            return True

        config = serialize_functions([sample])
        script = generate_injection_script(config)

        # Should have header comment and empty line
        lines = script.split('\n')
        assert lines[0].startswith('#')
        assert lines[1] == ''

    def test_empty_config(self):
        """Test generating script from empty config."""
        config = CustomFunctionsConfig(functions=[])
        script = generate_injection_script(config)

        # Should only contain header
        assert "# Custom functions injected" in script
        assert "def " not in script
