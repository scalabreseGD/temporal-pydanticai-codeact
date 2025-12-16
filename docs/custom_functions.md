## Custom Functions for Code Execution Agents

This document describes the custom function injection system for `CodeActAgent`, which allows you to define reusable helper functions in your codebase that are automatically serialized, analyzed for dependencies, and injected into the sandbox execution environment.

## Overview

The custom function system enables you to:

1. **Define functions in your Python codebase** - Write helper functions using normal Python syntax
2. **Automatic serialization** - Functions are serialized using `inspect.getsource()`
3. **Dependency detection** - Python's AST module analyzes imports to detect required packages
4. **Auto-installation** - Dependencies are automatically installed in Docker containers
5. ⭐ **Sync wrappers** - Async functions automatically wrapped for synchronous use (NO await needed!)
6. ⭐ **Full docstrings in signatures** - Agents see complete function documentation
7. **Sandbox injection** - Functions become available in sandbox code execution
8. **Type safety** - Functions maintain their type hints and signatures

## Why Use Custom Functions?

**vs. MCP Tools:** Custom functions are ideal for business logic and reusable utilities that you want to version control alongside your code, while MCP tools are better for external services and system integration.

**vs. Inline Code:** Custom functions provide:
- Reusability across multiple agents
- Better testing and maintainability
- Automatic dependency management
- Clear documentation in code

## Quick Start

### 1. Define Custom Functions

Create functions in your agent class:

```python
from temporal.pydanticai.codeact.agents.base.code_act_agent import CodeActAgent

class MyAgent(CodeActAgent):
    agent_name = 'my_agent'

    @staticmethod
    async def _get_custom_functions(**kwargs) -> list:
        """Define custom functions for this agent."""

        async def analyze_data(data_json: str) -> dict:
            """Analyze data using pandas."""
            import pandas as pd
            import numpy as np

            df = pd.read_json(data_json)
            return {
                'mean': df.mean().to_dict(),
                'std': df.std().to_dict()
            }

        def format_output(data: dict) -> str:
            """Format dictionary as markdown."""
            return "\\n".join(f"- **{k}**: {v}" for k, v in data.items())

        return [analyze_data, format_output]
```

### 2. Update Your Agent Prompts

Add custom function signatures to your instruction template:

```yaml
my_agent:
  system_prompt: "You are a data analysis assistant."
  instructions: |
    ## Available Custom Functions

    {% if custom_functions_signatures %}
    {% for sig in custom_functions_signatures %}
    ```python
    {{ sig }}
    ```
    {% endfor %}
    {% endif %}

    Use these functions in your execute_python code!
```

### 3. Use Functions in Generated Code

The agent can now call these functions in sandbox executions:

```python
# Agent generates code like this:
data = '[{"a": 1, "b": 2}, {"a": 3, "b": 4}]'
analysis = analyze_data(data)  # NO await needed! Async functions are wrapped
output = format_output(analysis)
print(output)
```

## Key Features

### ⭐ Automatic Sync Wrappers

**Async functions are automatically wrapped** so they can be called synchronously in the sandbox:

```python
# You define an async function:
async def fetch_and_process(url: str) -> dict:
    """Fetch and process data from URL."""
    import requests
    data = requests.get(url).json()
    return process(data)

# Agents see and use it as a SYNC function:
def fetch_and_process(url: str) -> dict:
    """Fetch and process data from URL."""
    # Sync wrapper automatically generated

# In sandbox code - NO await keyword needed!
result = fetch_and_process("https://api.example.com/data")  # Just works!
```

**Benefits:**
- 📝 Simpler sandbox code (no async/await complexity)
- 🔄 Works with existing event loops
- 🛡️ Robust error handling
- ⚡ Automatic `nest_asyncio` integration

### ⭐ Docstrings in Signatures

**Function signatures include complete docstrings** for better agent understanding:

```python
# Agents see the full documentation:
def analyze_dataframe(data_json: str) -> dict:
    """
    Analyze a pandas DataFrame from JSON.

    Args:
        data_json: JSON string representing the dataframe

    Returns:
        Dictionary with statistical analysis including:
        - mean: Average values for numeric columns
        - median: Median values
        - correlation: Correlation matrix
    """
```

**Benefits:**
- 📚 Agents understand parameter meanings
- 🎯 Better function selection
- ✅ Fewer usage errors
- 📖 Self-documenting code

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Agent Definition (_get_custom_functions)                 │
│    - Define functions with type hints                       │
│    - Functions can be sync or async                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 2. Serialization (serialize_functions)                      │
│    - Extract source: inspect.getsource()                    │
│    - ⭐ Generate sync wrapper if async (asyncio.run)        │
│    - Parse AST: ast.parse() + ast.walk()                    │
│    - Detect imports: Import/ImportFrom nodes                │
│    - Extract metadata: signature WITH docstring             │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 3. Integration (_build_agent)                               │
│    - Serialize functions → CustomFunctionsConfig            │
│    - Extract signatures for prompts                         │
│    - Pass to sandbox.code_sandbox_tools()                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 4. Execution (execute_python)                               │
│    - Install dependencies: pip install {packages}           │
│    - Generate injection script                              │
│    - Prepend to user code                                   │
│    - Execute with exec()                                    │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Agent startup** → `_get_custom_functions()` returns function list
2. **Serialization** → Functions converted to `SerializedFunction` models
3. **Agent build** → Signatures extracted for instruction templates
4. **Tool call** → `ExecutePythonArgs.custom_functions` populated
5. **Container execution** → Dependencies installed, functions injected
6. **Code execution** → Functions available in namespace

## Features

### Automatic Dependency Detection

The system uses Python's AST module to detect all import statements:

```python
async def my_function(data: str):
    import pandas as pd           # Detected: pandas
    from numpy import array       # Detected: numpy
    from scipy.stats import norm  # Detected: scipy
    import os                     # Filtered: stdlib

    # Function logic...
```

**Supported:**
- `import package`
- `import package as alias`
- `from package import item`
- `from package.submodule import item`
- Multiple imports: `import pkg1, pkg2`

**Automatic filtering:**
- Standard library modules excluded (os, sys, json, etc.)
- Only top-level package names extracted

### Async Function Support

Both sync and async functions are supported:

```python
# Sync function
def calculate(x: int) -> int:
    return x * 2

# Async function
async def fetch_and_analyze(url: str) -> dict:
    import requests
    data = requests.get(url).json()
    return analyze(data)
```

### Type Hints and Docstrings

Functions retain their type information and documentation:

```python
def process_data(
    input_data: list[int],
    threshold: float = 0.5
) -> dict[str, float]:
    """
    Process numerical data with threshold filtering.

    Args:
        input_data: List of integers to process
        threshold: Minimum value threshold

    Returns:
        Dictionary with statistical results
    """
    # Implementation...
```

This information is:
- Preserved in the serialized function
- Shown in instruction templates
- Available for agent reasoning

### Class Methods and Static Methods

The system fully supports serializing class methods and static methods:

```python
class MyAgent(CodeActAgent):
    @staticmethod
    async def _get_custom_functions(**kwargs):
        # Can return class static methods
        return [MyAgent.helper_method]

    @staticmethod
    async def helper_method(data: str) -> dict:
        """This static method can be serialized."""
        import pandas as pd
        df = pd.read_json(data)
        return df.to_dict()
```

**How it works:**
- `inspect.getsource()` extracts source with original indentation
- `textwrap.dedent()` removes leading whitespace before parsing
- Dependencies detected correctly regardless of indentation
- Works for `@staticmethod`, `@classmethod`, and regular methods

### State Persistence

Custom functions work seamlessly with state persistence:

```python
# First execution
data = load_data()
processed = analyze_data(data)  # Custom function - NO await needed!

# Second execution (after restart)
# Functions are re-injected automatically
more_analysis = analyze_data(processed)  # Still works!
```

## API Reference

### Core Classes

#### `SerializedFunction`

```python
class SerializedFunction(BaseModel):
    name: str                      # Function name
    source_code: str               # Complete source code
    dependencies: List[str]        # Package dependencies
    is_async: bool                 # Async flag
    signature: Optional[str]       # Function signature
    docstring: Optional[str]       # Documentation
```

#### `CustomFunctionsConfig`

```python
class CustomFunctionsConfig(BaseModel):
    functions: List[SerializedFunction]

    def get_all_dependencies(self) -> List[str]:
        """Get deduplicated list of all dependencies."""

    def get_function_by_name(self, name: str) -> Optional[SerializedFunction]:
        """Find function by name."""

    def get_all_signatures(self) -> List[str]:
        """Get all function signatures for documentation."""
```

### Serialization Functions

```python
from temporal.pydanticai.codeact.utils.function_serializer import (
    serialize_function,
    serialize_functions,
    parse_dependencies,
    generate_injection_script
)

# Serialize single function
serialized = serialize_function(my_func)

# Serialize multiple functions
config = serialize_functions([func1, func2, func3])

# Parse dependencies from source code
deps = parse_dependencies(source_code_string)

# Generate injection script
script = generate_injection_script(config)
```

### Agent Integration

```python
class MyAgent(CodeActAgent):
    @staticmethod
    async def _get_custom_functions(**kwargs) -> list:
        """Override to provide custom functions."""
        return [func1, func2]  # Return list of callables
```

### Sandbox Integration

```python
from temporal.pydanticai.codeact.datamodels.sandbox import ExecutePythonArgs

# Execute code with custom functions
result = await sandbox.execute_python(
    ExecutePythonArgs(
        container_id=container_id,
        code=user_code,
        custom_functions=functions_config
    )
)
```

## Best Practices

### ✅ Do

- **Define focused, single-purpose functions**
  ```python
  async def calculate_statistics(data: list) -> dict:
      # Good: Does one thing well
  ```

- **Use type hints for clarity**
  ```python
  def process(data: pd.DataFrame) -> dict[str, Any]:
      # Good: Clear types help agents understand usage
  ```

- **Include comprehensive docstrings**
  ```python
  def analyze(data):
      """
      Analyze dataset and return statistics.

      Args:
          data: Input dataset as list or dict

      Returns:
          Dictionary with mean, median, std
      """
  ```

- **Keep imports inside functions**
  ```python
  def use_pandas(data):
      import pandas as pd  # Good: Imports detected
      return pd.DataFrame(data)
  ```

- **Test functions independently**
  ```python
  # Write unit tests for your custom functions
  def test_analyze_data():
      result = analyze_data('[{"a": 1}]')
      assert 'mean' in result
  ```

### ❌ Don't

- **Don't use external file dependencies**
  ```python
  def load_config():
      with open('/local/config.json') as f:  # Bad: File might not exist
          return json.load(f)
  ```

- **Don't rely on module-level state**
  ```python
  CACHE = {}  # Bad: Won't persist in sandbox

  def cached_computation(x):
      if x in CACHE:
          return CACHE[x]
  ```

- **Don't use non-serializable closures**
  ```python
  def outer():
      db_connection = connect()  # Bad: closure over connection

      def inner(query):
          return db_connection.execute(query)

      return inner
  ```

- **Don't forget to handle errors**
  ```python
  def risky_operation(data):
      return data / 0  # Bad: Should handle division errors
  ```

## Examples

### Example 1: Data Analysis Agent

See `examples/data_analysis_agent.py` for a complete implementation featuring:

- Statistical analysis functions
- DataFrame processing
- Multiple dependencies (pandas, numpy, scipy)
- Integration with MCP tools
- Comprehensive documentation

```python
class DataAnalysisAgent(CodeActAgent):
    agent_name = 'data_analysis_agent'

    @staticmethod
    async def _get_custom_functions(**kwargs) -> list:
        async def analyze_dataframe(data_json: str) -> dict:
            import pandas as pd
            import numpy as np
            df = pd.read_json(data_json)
            return {
                'mean': df.mean().to_dict(),
                'correlation': df.corr().to_dict()
            }

        async def calculate_statistics(values: list) -> dict:
            import numpy as np
            from scipy import stats
            arr = np.array(values)
            return {
                'mean': float(np.mean(arr)),
                'skewness': float(stats.skew(arr))
            }

        return [analyze_dataframe, calculate_statistics]
```

### Example 2: Text Processing Agent

```python
class TextProcessorAgent(CodeActAgent):
    agent_name = 'text_processor'

    @staticmethod
    async def _get_custom_functions(**kwargs) -> list:
        def extract_keywords(text: str, top_n: int = 10) -> list:
            """Extract top keywords using TF-IDF."""
            from sklearn.feature_extraction.text import TfidfVectorizer
            vectorizer = TfidfVectorizer(max_features=top_n)
            vectorizer.fit([text])
            return vectorizer.get_feature_names_out().tolist()

        def sentiment_analysis(text: str) -> dict:
            """Analyze sentiment using TextBlob."""
            from textblob import TextBlob
            blob = TextBlob(text)
            return {
                'polarity': blob.sentiment.polarity,
                'subjectivity': blob.sentiment.subjectivity
            }

        return [extract_keywords, sentiment_analysis]
```

### Example 3: Mathematical Computations

```python
class MathAgent(CodeActAgent):
    agent_name = 'math_agent'

    @staticmethod
    async def _get_custom_functions(**kwargs) -> list:
        def solve_linear_system(A: list, b: list) -> list:
            """Solve Ax = b using numpy."""
            import numpy as np
            A_arr = np.array(A)
            b_arr = np.array(b)
            return np.linalg.solve(A_arr, b_arr).tolist()

        def integrate_function(expr: str, var: str, lower: float, upper: float) -> float:
            """Symbolically integrate and evaluate."""
            from sympy import symbols, integrate, sympify
            x = symbols(var)
            expression = sympify(expr)
            result = integrate(expression, (x, lower, upper))
            return float(result)

        return [solve_linear_system, integrate_function]
```

## Troubleshooting

### Function Not Found in Sandbox

**Problem:** `NameError: name 'my_function' is not defined`

**Solutions:**
1. Verify function is returned from `_get_custom_functions()`
2. Check `custom_functions_config` is passed to sandbox tools
3. Ensure agent rebuild after adding functions

### Dependencies Not Installing

**Problem:** `ModuleNotFoundError: No module named 'package'`

**Solutions:**
1. Check imports are inside function body
2. Verify AST parsing detected the import: `config.get_all_dependencies()`
3. Test dependency installation manually: `pip install package`
4. Check for typos in package names

### Function Source Not Extractable

**Problem:** `ValueError: Cannot extract source for function`

**Solutions:**
1. Don't use lambda functions: `lambda x: x * 2` ❌
2. Don't use built-in functions: `len`, `sum` ❌
3. Define functions in module scope, not dynamically
4. Ensure function is defined in a `.py` file

### Async/Await Issues

**Problem:** `RuntimeError: no running event loop`

**Solution:**
✅ **No action needed!** Async functions are automatically wrapped with synchronous wrappers. You can define functions as `async def` but call them without `await` in sandbox code:

```python
# Define async function:
async def my_function(data):
    # async logic
    return result

# Call it as sync in sandbox - NO await needed:
result = my_function(data)  # Works automatically!
```

The sync wrapper handles all event loop management internally using `asyncio.run()` and `nest_asyncio`.

## Performance Considerations

### Dependency Installation

- **First execution**: Dependencies installed (~10-30s depending on packages)
- **Subsequent executions**: Packages cached in container
- **Tip**: Use lightweight packages when possible
- **Tip**: Pre-install common packages in base Docker image

### Function Injection Overhead

- **Negligible** for < 10 functions
- **Minimal** (~100ms) for source code serialization
- **One-time** per container startup

### Best Practices

1. **Reuse containers** - Dependencies only install once per container
2. **Group related functions** - Create focused agents with related functions
3. **Avoid heavy imports** - Import only what you need inside functions
4. **Cache results** - Use state persistence for expensive computations

## Future Enhancements

Potential improvements under consideration:

- [ ] Pre-compile functions to bytecode
- [ ] Support for class definitions
- [ ] Automatic version pinning for dependencies
- [ ] Function caching across containers
- [ ] IDE autocomplete support
- [ ] Dependency conflict resolution

## Related Documentation

- [Agent Architecture](architecture.md) - Overall agent system design
- [MCP Integration](../CLAUDE.md#mcp-server-integration) - External tool integration
- [Sandbox Documentation](../README.md#persistent-storage) - Container execution details
- [Testing Guide](../tests/README.md) - Testing custom functions

## Support

For issues, questions, or feature requests related to custom functions:

1. Check existing tests: `tests/temporal/pydanticai/codeact/test_function_serializer.py`
2. Review example: `examples/data_analysis_agent.py`
3. File an issue on GitHub with:
   - Function definition
   - Serialization output
   - Error messages
   - Expected vs actual behavior
