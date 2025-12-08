# Practical Examples

Real-world examples demonstrating Code Act PydanticAI capabilities.

## Table of Contents

1. [Simple Math Agent](#1-simple-math-agent)
2. [Data Analysis Agent](#2-data-analysis-agent)
3. [Multi-Step Calculation](#3-multi-step-calculation-with-state)
4. [Direct Sandbox Usage](#4-direct-sandbox-usage-no-agent)
5. [Custom Agent](#5-custom-agent-extension)

---

## 1. Simple Math Agent

Basic agent executing Python calculations.

```python
import asyncio
from activities.common import load_config, get_temporal_client
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

async def simple_math_example():
    config = load_config()
    client = await get_temporal_client(
        config['temporal'],
        plugins=[PydanticAIPlugin()]
    )

    result = await client.execute_workflow(
        'SimpleAgentWorkflow',
        arg='Calculate the sum of squares from 1 to 100',
        id='math-agent-1',
        task_queue='sample_queue'
    )

    print(result)

asyncio.run(simple_math_example())
```

**Expected Output:**
```
The sum of squares from 1 to 100 is 338,350.

Calculated using: sum(i**2 for i in range(1, 101))
```

---

## 2. Data Analysis Agent

Agent performing pandas data analysis.

```python
async def data_analysis_example():
    config = load_config()
    client = await get_temporal_client(
        config['temporal'],
        plugins=[PydanticAIPlugin()]
    )

    task = """
    Generate a random pandas DataFrame with 100 rows and 4 columns (A, B, C, D).
    Calculate:
    1. Summary statistics for each column
    2. Correlation matrix
    3. Mean of column A where B > 0.5

    Present the results clearly.
    """

    result = await client.execute_workflow(
        'SimpleAgentWorkflow',
        arg=task,
        id='data-analysis-1',
        task_queue='sample_queue'
    )

    print(result)

asyncio.run(data_analysis_example())
```

**Agent Actions:**
1. Generates DataFrame with `np.random.rand(100, 4)`
2. Uses `df.describe()` for statistics
3. Uses `df.corr()` for correlation
4. Filters and calculates mean
5. Formats output

---

## 3. Multi-Step Calculation with State

Demonstrating persistent state across executions.

```python
from datamodels.sandbox import (
    SandboxInputTask, SandboxTaskTypes,
    StartContainerArgs, ExecutePythonArgs,
    SandboxBaseArgs
)

async def multi_step_example():
    config = load_config()
    client = await get_temporal_client(config['temporal'])

    workflow_id = "multi-step-calc"

    # Start workflow
    handle = await client.start_workflow(
        'SandboxWorkflow',
        id=workflow_id,
        task_queue='sample_queue'
    )

    # Step 1: Start container
    await handle.signal('submit_task', SandboxInputTask(
        task_name=SandboxTaskTypes.START_CONTAINER,
        task_args=StartContainerArgs(python_packages=["numpy"])
    ))
    container_id = await wait_for_result(handle)

    # Step 2: Generate data
    await handle.signal('submit_task', SandboxInputTask(
        task_name=SandboxTaskTypes.EXECUTE_PYTHON,
        task_args=ExecutePythonArgs(
            container_id=container_id,
            code="""
import numpy as np
data = np.random.normal(100, 15, 1000)
print(f"Generated {len(data)} samples")
"""
        )
    ))
    result = await wait_for_result(handle)
    print(f"Step 2: {result['output']}")

    # Step 3: Calculate statistics (uses 'data' from Step 2)
    await handle.signal('submit_task', SandboxInputTask(
        task_name=SandboxTaskTypes.EXECUTE_PYTHON,
        task_args=ExecutePythonArgs(
            container_id=container_id,
            code="""
mean = np.mean(data)
std = np.std(data)
print(f"Mean: {mean:.2f}, Std: {std:.2f}")
"""
        )
    ))
    result = await wait_for_result(handle)
    print(f"Step 3: {result['output']}")

    # Step 4: Calculate percentiles (uses 'data')
    await handle.signal('submit_task', SandboxInputTask(
        task_name=SandboxTaskTypes.EXECUTE_PYTHON,
        task_args=ExecutePythonArgs(
            container_id=container_id,
            code="""
p25, p50, p75 = np.percentile(data, [25, 50, 75])
print(f"25th: {p25:.2f}, 50th: {p50:.2f}, 75th: {p75:.2f}")
"""
        )
    ))
    result = await wait_for_result(handle)
    print(f"Step 4: {result['output']}")

    # Cleanup
    await handle.signal('submit_task', SandboxInputTask(
        task_name=SandboxTaskTypes.STOP_CONTAINER,
        task_args=SandboxBaseArgs(container_id=container_id)
    ))
    await handle.signal('stop_workflow')
    await handle.result()

asyncio.run(multi_step_example())
```

---

## 4. Direct Sandbox Usage (No Agent)

Using sandbox directly without AI agent.

```python
from docker_sandbox.container_sandbox import PersistentContainerSandbox
from datamodels.sandbox import StartContainerArgs, ExecutePythonArgs, SandboxBaseArgs

async def direct_sandbox_example():
    sandbox = PersistentContainerSandbox()

    # Start container
    container_id = await sandbox.start_container(
        StartContainerArgs(python_packages=["pandas"])
    )

    try:
        # Execute code
        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container_id,
                code="""
import pandas as pd
df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
print(df.to_string())
"""
            )
        )

        print("Output:", result['output'])

        # Query state
        state = await sandbox.get_python_state(
            SandboxBaseArgs(container_id=container_id)
        )
        print("State variables:", list(state.keys()))

    finally:
        # Cleanup
        await sandbox.stop_container(
            SandboxBaseArgs(container_id=container_id)
        )

asyncio.run(direct_sandbox_example())
```

---

## 5. Custom Agent Extension

Create a specialized agent extending CodeActAgent.

```python
# src/agents/data_science_agent.py
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.base.code_act_agent import CodeActAgent

class DataScienceAgent(CodeActAgent):
    """Specialized agent for data science tasks."""
    agent_name = 'data_science_agent'

    # Could override methods to add custom behavior:
    # - Custom MCP tools
    # - Specialized system prompt
    # - Pre-configured packages
```

Create corresponding prompts in `agent_prompts.yml`:

```yaml
data_science_agent:
  system_prompt: |
    You are an expert data scientist with access to a Python sandbox.
    You specialize in exploratory data analysis, statistical modeling,
    and data visualization.

  instructions: |
    Container ID: {{ container_id }}
    Available packages: {{ python_packages }}

    For data science tasks:
    1. Start with exploratory data analysis
    2. Check data quality (missing values, outliers)
    3. Use appropriate statistical methods
    4. Visualize results when helpful
    5. Explain your methodology

    Use execute_python tool for all computations.
```

Use the custom agent:

```python
# src/workflows/data_science_workflow.py
from datamodels.agent_builder import AgentBuilder
from agents.data_science_agent import DataScienceAgent

@workflow.defn
class DataScienceWorkflow(CodeActAgentWorkflow):
    @workflow.run
    async def run(self, user_task: str) -> str:
        await self.start_sandbox_container(
            python_packages=["pandas", "numpy", "scipy", "matplotlib", "seaborn"]
        )

        try:
            prompts = await self._get_prompts()
            configs = await self._get_configs()

            agent = await DataScienceAgent.from_agent_confs(
                agent_builder=AgentBuilder(
                    prompts=prompts,
                    model_configs=configs['llm']['gemini']
                )
            )

            result = await agent.run(
                user_prompt=user_task,
                deps=CodeActAgentDeps(
                    container_id=self.container_id,
                    python_packages=["pandas", "numpy", "scipy", "matplotlib", "seaborn"]
                )
            )

            return result.output

        finally:
            await self.stop_sandbox_container()
```

---

## Common Patterns

### Pattern 1: Error Handling

```python
result = await sandbox.execute_python(ExecutePythonArgs(...))

if result['success']:
    print("Success:", result['output'])
else:
    print("Error:", result['error'])
    print("Exit code:", result['exit_code'])
    # Handle error appropriately
```

### Pattern 2: Variable Injection

```python
# Pre-load data into execution
result = await sandbox.execute_python(
    ExecutePythonArgs(
        container_id=container_id,
        code="""
print(f"Processing {len(data)} items...")
result = sum(data)
print(f"Sum: {result}")
""",
        variables={"data": [1, 2, 3, 4, 5]}
    )
)
```

### Pattern 3: Multi-File Operations

```python
# Write multiple files
for filename, content in files.items():
    await sandbox.write_file(WriteFileArgs(
        container_id=container_id,
        path=f"/tmp/{filename}",
        content=content
    ))

# Process files
await sandbox.execute_python(ExecutePythonArgs(
    container_id=container_id,
    code="""
import glob
files = glob.glob('/tmp/*.csv')
print(f"Found {len(files)} CSV files")
"""
))
```

### Pattern 4: Incremental Analysis

```python
# Load data
await sandbox.execute_python(ExecutePythonArgs(
    container_id=container_id,
    code="import pandas as pd\ndf = pd.read_csv('/tmp/data.csv')"
))

# Step-by-step analysis using persisted 'df'
for analysis in ["df.info()", "df.describe()", "df.corr()"]:
    await sandbox.execute_python(ExecutePythonArgs(
        container_id=container_id,
        code=f"print({analysis})"
    ))
```

---

## Testing Examples

### Unit Test for Sandbox

```python
import pytest
from docker_sandbox.container_sandbox import PersistentContainerSandbox
from datamodels.sandbox import StartContainerArgs, ExecutePythonArgs

@pytest.mark.asyncio
async def test_persistent_state():
    sandbox = PersistentContainerSandbox()
    container_id = await sandbox.start_container(StartContainerArgs())

    try:
        # Set variable
        result1 = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container_id,
                code="x = 42"
            )
        )
        assert result1['success']

        # Read variable in new execution
        result2 = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container_id,
                code="print(x)"
            )
        )
        assert result2['success']
        assert "42" in result2['output']

    finally:
        await sandbox.stop_container(SandboxBaseArgs(container_id=container_id))
```

---

## See Also

- [Sandbox Operations](sandbox-operations.md) - Complete operation reference
- [API Reference](api-reference.md) - Full API documentation
- [Sandbox Workflow Demo](sandbox_workflow_demo.md) - Detailed walkthrough
- [Architecture](architecture.md) - How it all works together
