# Sync Wrapper Implementation for Custom Functions

## Overview

Custom functions are now **automatically wrapped with synchronous wrappers** when they are async, and **function signatures include full docstrings** to provide better context to AI agents.

## Key Changes

### 1. ✅ Docstrings in Signatures

**Problem:** Function signatures showed only the function declaration line:
```python
def search(query: str) -> list:
```

**Solution:** Signatures now include the complete docstring:
```python
def search(query: str) -> list:
    """
    Search using DuckDuckGo.

    Args:
        query: Search term

    Returns:
        List of search results
    """
```

### 2. ✅ Sync Wrappers for Async Functions

**Problem:** Async functions required `await` in sandbox code, which could be confusing:
```python
# User had to write:
result = await duckduckgo_text_search("python")
```

**Solution:** Async functions are automatically wrapped with sync wrappers:
```python
# Now users can write:
result = duckduckgo_text_search("python")  # No await needed!
```

**How it works:**
1. Original async function is renamed to `__async_{function_name}`
2. Sync wrapper with original name is generated
3. Wrapper calls async function using `asyncio.run()`
4. Both functions are injected into sandbox

## Implementation Details

### Sync Wrapper Generation

For an async function like:
```python
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    import requests
    return requests.get(url).json()
```

The system generates:
```python
# Original async function (renamed)
async def __async_fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    import requests
    return requests.get(url).json()

# Sync wrapper (same name as original)
def fetch_data(url: str) -> dict:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, use nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(__async_fetch_data(url))
        else:
            return asyncio.run(__async_fetch_data(url))
    except RuntimeError:
        # Fallback for environments without event loop
        return asyncio.run(__async_fetch_data(url))
```

### Docstring Extraction with Fallback

Standard Python docstrings must be the first statement in a function. However, some functions have docstrings after imports:

```python
async def my_func():
    from module import something  # Import first
    """This is not a valid Python docstring!"""  # Too late!
    pass
```

**Solution:** The system uses a two-step approach:

1. **Try `inspect.getdoc()`** - Standard Python docstring extraction
2. **Fallback to regex** - If no docstring found, search for triple-quoted strings in source

This ensures docstrings are captured even when improperly placed.

## API Changes

### `extract_function_signature(func, include_docstring=True)`

**New parameter:** `include_docstring`
- Default: `True` (include docstring in signature)
- Set to `False` to get only the function declaration line

**Example:**
```python
from temporal.pydanticai.codeact.utils.function_serializer import extract_function_signature

def my_func(x: int) -> str:
    """Convert int to string."""
    return str(x)

# With docstring (default)
sig = extract_function_signature(my_func)
print(sig)
# Output:
# def my_func(x: int) -> str:
#     """
#     Convert int to string.
#     """

# Without docstring
sig = extract_function_signature(my_func, include_docstring=False)
print(sig)
# Output:
# def my_func(x: int) -> str:
```

### `serialize_function(func)`

**New behavior:**
- Automatically generates sync wrapper for async functions
- Adds `nest_asyncio` to dependencies when async functions are detected
- Signatures always show sync version (no `async def`)

**Example:**
```python
from temporal.pydanticai.codeact.utils.function_serializer import serialize_function

async def async_func(x: int) -> int:
    """Multiply by 2."""
    return x * 2

serialized = serialize_function(async_func)

print(serialized.name)           # "async_func"
print(serialized.is_async)       # True (original was async)
print(serialized.dependencies)   # ['nest_asyncio'] (added automatically)

# Signature is SYNC
print(serialized.signature)
# Output:
# def async_func(x: int) -> int:
#     """
#     Multiply by 2.
#     """

# Source code contains both async and sync versions
print("__async_async_func" in serialized.source_code)  # True (renamed async)
print("def async_func" in serialized.source_code)      # True (sync wrapper)
print("asyncio.run" in serialized.source_code)         # True (wrapper logic)
```

## Usage in Agents

### Before (Async Required)

```python
class MyAgent(CodeActAgent):
    @staticmethod
    async def _get_custom_functions(**kwargs):
        async def search(query: str) -> list:
            """Search function."""
            from duckduckgo_search import DDGS
            return DDGS().text(query)
        return [search]

# Agent prompt would need to explain await:
# "Use: result = await search('python')"
```

### After (Sync Automatic)

```python
class MyAgent(CodeActAgent):
    @staticmethod
    async def _get_custom_functions(**kwargs):
        async def search(query: str) -> list:
            """
            Search using DuckDuckGo.

            Args:
                query: Search term

            Returns:
                List of search results
            """
            from duckduckgo_search import DDGS
            return DDGS().text(query)
        return [search]

# Agent sees in prompt:
# def search(query: str) -> list:
#     """
#     Search using DuckDuckGo.
#
#     Args:
#         query: Search term
#
#     Returns:
#         List of search results
#     """
#
# Agent can use: result = search('python')  # No await!
```

## Benefits

### 1. **Simpler User Code**

Users don't need to use `await` in sandbox code:
```python
# Before:
result = await my_async_func(data)

# After:
result = my_async_func(data)  # Just works!
```

### 2. **Better Agent Understanding**

Agents see full docstrings with parameter descriptions, return types, and examples directly in the function signature.

### 3. **Backwards Compatible**

- Sync functions work unchanged
- Existing async functions get wrapped automatically
- No breaking changes to existing code

### 4. **Flexible Event Loop Handling**

The sync wrapper handles various event loop scenarios:
- No event loop: Uses `asyncio.run()`
- Existing loop not running: Uses `asyncio.run()`
- Existing loop running: Uses `nest_asyncio` for nested execution

## Testing

All tests updated and passing (32/32):

```bash
pytest tests/temporal/pydanticai/codeact/test_function_serializer.py -v
# ✅ 32 passed
```

**Key test cases:**
- ✅ Sync wrapper generation for async functions
- ✅ Docstring inclusion in signatures
- ✅ Dependency detection (nest_asyncio added)
- ✅ Fallback docstring extraction
- ✅ Proper function renaming (`__async_` prefix)
- ✅ Event loop handling

## Dependencies

**New dependency added automatically:**
- `nest_asyncio` - Added when async functions are serialized
- Enables nested event loop execution when needed
- Installed automatically in containers during function injection

## Migration Guide

### No Action Required!

Existing code works without changes. Async functions are automatically wrapped.

### Optional: Improve Docstrings

For best results, ensure docstrings are properly placed:

```python
# ❌ Docstring after import (still works, but better to fix)
async def func():
    import pandas
    """This works but is non-standard."""
    pass

# ✅ Docstring as first statement (recommended)
async def func():
    """This is the standard way."""
    import pandas
    pass
```

## Limitations

1. **Nested Functions:** Sync wrappers work for top-level functions and methods. Nested functions inside other functions may have limitations.

2. **Event Loop Edge Cases:** While the wrapper handles most scenarios, some advanced event loop manipulations might require manual handling.

3. **Performance:** Slight overhead from `asyncio.run()` calls. For performance-critical code, consider using sync functions directly.

## Future Enhancements

- [ ] Support for async context managers (`async with`)
- [ ] Optimization of wrapper code for repeated calls
- [ ] Better error messages when async/sync conflicts occur
- [ ] Custom wrapper templates for specific use cases

## Examples

See:
- `src/example/agents/simple_agent.py` - Real-world usage with `duckduckgo_text_search`
- `examples/data_analysis_agent.py` - Multiple async functions with complex logic
- `tests/temporal/pydanticai/codeact/test_function_serializer.py` - Comprehensive test coverage

## Summary

✅ **Docstrings in signatures** - Agents see full documentation
✅ **Automatic sync wrappers** - No more `await` in sandbox code
✅ **Fallback docstring extraction** - Works even with improperly placed docstrings
✅ **Event loop handling** - Robust async execution in various scenarios
✅ **Backwards compatible** - Existing code works unchanged
✅ **Fully tested** - 32/32 tests passing

The system now provides a seamless experience for using async functions in the sandbox while giving agents complete documentation context!
