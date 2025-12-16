"""
Function serialization utilities with automatic dependency detection.

This module provides utilities to extract function source code using inspect,
parse dependencies using Python's AST module, and serialize functions for
injection into sandbox execution environments.
"""

import ast
import inspect
import textwrap
from typing import Callable, List, Set

from temporal.pydanticai.codeact.datamodels.custom_functions import SerializedFunction, CustomFunctionsConfig


class DependencyExtractor(ast.NodeVisitor):
    """
    AST NodeVisitor that extracts import statements from Python code.

    Walks the AST tree and collects all imported package names from
    both 'import' and 'from...import' statements.
    """

    def __init__(self):
        self.dependencies: Set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """
        Visit an 'import' statement node.

        Example: import pandas, numpy as np
        Extracts: ['pandas', 'numpy']
        """
        for alias in node.names:
            # Get the top-level package name
            package_name = alias.name.split('.')[0]
            self.dependencies.add(package_name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """
        Visit a 'from...import' statement node.

        Example: from pandas.core import DataFrame
        Extracts: ['pandas']
        """
        if node.module:
            # Get the top-level package name
            package_name = node.module.split('.')[0]
            self.dependencies.add(package_name)
        self.generic_visit(node)


def extract_function_source(func: Callable) -> str:
    """
    Extract the complete source code of a function.

    Args:
        func: The function to extract source from

    Returns:
        Complete source code as a string

    Raises:
        OSError: If source code cannot be retrieved
        TypeError: If func is not a function
    """
    try:
        source = inspect.getsource(func)
        return source
    except (OSError, TypeError) as e:
        raise ValueError(f"Cannot extract source for function {func.__name__}: {e}")


def parse_dependencies(source_code: str) -> List[str]:
    """
    Parse Python source code to extract all imported package dependencies.

    Uses Python's AST module to walk the abstract syntax tree and find
    all Import and ImportFrom nodes, extracting top-level package names.

    Handles indented source code (e.g., from methods) by removing leading whitespace.

    Args:
        source_code: Python source code as a string

    Returns:
        Sorted list of unique top-level package names

    Example:
        >>> code = '''
        ... import pandas as pd
        ... from numpy import array
        ... import matplotlib.pyplot as plt
        ... '''
        >>> parse_dependencies(code)
        ['matplotlib', 'numpy', 'pandas']
    """
    # Remove leading indentation to handle source extracted from class methods
    dedented_code = textwrap.dedent(source_code)

    try:
        tree = ast.parse(dedented_code)
    except SyntaxError as e:
        raise ValueError(f"Cannot parse source code: {e}")

    extractor = DependencyExtractor()
    extractor.visit(tree)

    # Filter out standard library modules (basic heuristic)
    # Note: This is a simple filter - could be enhanced with stdlib-list package
    stdlib_modules = {
        'os', 'sys', 'json', 'datetime', 'time', 'random', 're', 'math',
        'collections', 'itertools', 'functools', 'pathlib', 'typing',
        'asyncio', 'concurrent', 'threading', 'multiprocessing',
        'logging', 'unittest', 'pickle', 'copy', 'dataclasses'
    }

    external_deps = [dep for dep in extractor.dependencies if dep not in stdlib_modules]
    return sorted(external_deps)


def extract_function_signature(func: Callable, include_docstring: bool = True) -> str:
    """
    Extract a human-readable function signature with optional docstring.

    Args:
        func: The function to extract signature from
        include_docstring: Whether to include the docstring (default: True)

    Returns:
        Function signature with docstring formatted as code block
    """
    try:
        sig = inspect.signature(func)
        func_name = func.__name__

        # Always generate sync signature (async functions will be wrapped)
        prefix = "def"

        signature_line = f"{prefix} {func_name}{sig}:"

        # Add docstring if requested
        if include_docstring:
            docstring = extract_function_docstring(func)
            if docstring:
                # Format docstring with proper indentation
                lines = [signature_line]
                lines.append(f'    """')
                # Handle multi-line docstrings
                for line in docstring.split('\n'):
                    lines.append(f'    {line}' if line.strip() else '    ')
                lines.append(f'    """')
                return '\n'.join(lines)

        return signature_line
    except (ValueError, TypeError):
        # Fallback if signature cannot be extracted
        return f"def {func.__name__}(...):"


def extract_function_docstring(func: Callable) -> str | None:
    """
    Extract the docstring from a function.

    Uses inspect.getdoc() first, but falls back to parsing the source code
    for docstring-like strings if the function doesn't have a proper docstring
    (e.g., docstring placed after imports).

    Args:
        func: The function to extract docstring from

    Returns:
        Docstring if present, None otherwise
    """
    # Try standard docstring extraction first
    docstring = inspect.getdoc(func)
    if docstring:
        return docstring

    # Fallback: try to extract docstring-like strings from source
    try:
        source = inspect.getsource(func)
        dedented = textwrap.dedent(source)

        # Look for triple-quoted strings in the function body
        import re
        # Try """ first, then '''
        pattern_double = r'"""(.*?)"""'
        pattern_single = r"'''(.*?)'''"

        matches = re.findall(pattern_double, dedented, re.DOTALL)
        if not matches:
            matches = re.findall(pattern_single, dedented, re.DOTALL)

        if matches:
            # Return the first docstring-like string found
            return matches[0].strip()

    except (OSError, TypeError):
        pass

    return None


def is_async_function(func: Callable) -> bool:
    """
    Check if a function is async.

    Args:
        func: The function to check

    Returns:
        True if the function is async, False otherwise
    """
    return inspect.iscoroutinefunction(func)


def generate_sync_wrapper(func: Callable, source_code: str) -> str:
    """
    Generate a sync wrapper for an async function.

    Creates a synchronous wrapper function that calls the async function
    using asyncio.run(). This allows async functions to be called
    synchronously in the sandbox environment.

    Args:
        func: The async function to wrap
        source_code: Original source code of the async function

    Returns:
        Source code for both the original async function (renamed) and sync wrapper

    Example:
        Original:
        ```python
        async def fetch_data(url: str) -> dict:
            import requests
            return requests.get(url).json()
        ```

        Generated:
        ```python
        async def __async_fetch_data(url: str) -> dict:
            import requests
            return requests.get(url).json()

        def fetch_data(url: str) -> dict:
            import asyncio
            return asyncio.run(__async_fetch_data(url))
        ```
    """
    func_name = func.__name__
    async_name = f"__async_{func_name}"

    # Replace function name in source with async variant
    dedented_source = textwrap.dedent(source_code)

    # Replace the function definition line
    # Handle both "async def func_name" and potential decorators
    import re
    pattern = rf'(async\s+)?def\s+{re.escape(func_name)}\s*\('
    dedented_source = re.sub(pattern, f'async def {async_name}(', dedented_source, count=1)

    # Extract signature for wrapper
    try:
        sig = inspect.signature(func)
        param_names = [param.name for param in sig.parameters.values()]
        call_args = ', '.join(param_names)

        # Generate sync wrapper (sig already includes return type annotation)
        wrapper_code = f"""
def {func_name}{sig}:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a new one
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete({async_name}({call_args}))
        else:
            return asyncio.run({async_name}({call_args}))
    except RuntimeError:
        # Fallback for environments without event loop
        return asyncio.run({async_name}({call_args}))
"""

        return dedented_source + "\n" + textwrap.dedent(wrapper_code)

    except Exception:
        # Fallback: simpler wrapper without signature preservation
        return dedented_source + f"""
def {func_name}(*args, **kwargs):
    import asyncio
    return asyncio.run({async_name}(*args, **kwargs))
"""


def serialize_function(func: Callable) -> SerializedFunction:
    """
    Serialize a function with automatic dependency detection and sync wrapper generation.

    Combines source extraction, AST parsing, and metadata extraction
    to create a complete SerializedFunction model. Async functions are
    automatically wrapped with synchronous wrappers that use asyncio.run().

    Args:
        func: The function to serialize

    Returns:
        SerializedFunction model with all metadata

    Raises:
        ValueError: If function cannot be serialized

    Example:
        >>> async def analyze_data(df_json: str) -> dict:
        ...     import pandas as pd
        ...     df = pd.read_json(df_json)
        ...     return {'mean': df.mean().to_dict()}
        ...
        >>> serialized = serialize_function(analyze_data)
        >>> serialized.name
        'analyze_data'
        >>> serialized.is_async
        True
        >>> 'def analyze_data' in serialized.source_code  # Sync wrapper generated
        True
        >>> serialized.dependencies
        ['pandas']
    """
    # Extract source code
    source_code = extract_function_source(func)

    # Check if async and generate sync wrapper if needed
    is_async = is_async_function(func)
    if is_async:
        # Generate sync wrapper for async function
        source_code = generate_sync_wrapper(func, source_code)

    # Parse dependencies from source (before wrapping to get accurate deps)
    dependencies = parse_dependencies(source_code)

    # Extract metadata (signature is always sync now)
    signature = extract_function_signature(func, include_docstring=True)
    docstring = extract_function_docstring(func)

    return SerializedFunction(
        name=func.__name__,
        source_code=source_code,
        dependencies=dependencies,
        is_async=is_async,  # Original async status for reference
        signature=signature,
        docstring=docstring
    )


def serialize_functions(funcs: List[Callable]) -> CustomFunctionsConfig:
    """
    Serialize multiple functions into a CustomFunctionsConfig.

    Args:
        funcs: List of functions to serialize

    Returns:
        CustomFunctionsConfig containing all serialized functions

    Raises:
        ValueError: If any function cannot be serialized

    Example:
        >>> def helper1(x): return x * 2
        >>> def helper2(y): return y + 1
        >>> config = serialize_functions([helper1, helper2])
        >>> len(config.functions)
        2
    """
    serialized = []
    errors = []

    for func in funcs:
        try:
            serialized.append(serialize_function(func))
        except ValueError as e:
            errors.append(f"{func.__name__}: {e}")

    if errors:
        raise ValueError(f"Failed to serialize functions: {', '.join(errors)}")

    return CustomFunctionsConfig(functions=serialized)


def generate_injection_script(config: CustomFunctionsConfig) -> str:
    """
    Generate Python code to inject all functions into execution environment.

    Combines all function source codes into a single script that can be
    prepended to user code.

    Args:
        config: CustomFunctionsConfig with functions to inject

    Returns:
        Python code string with all function definitions

    Example:
        >>> config = CustomFunctionsConfig(functions=[...])
        >>> script = generate_injection_script(config)
        >>> # script contains all function definitions ready to exec()
    """
    parts = [
        "# Custom functions injected by temporal.pydanticai.codeact",
        ""
    ]

    for func in config.functions:
        parts.append(func.source_code)
        parts.append("")  # Empty line between functions

    return "\n".join(parts)
