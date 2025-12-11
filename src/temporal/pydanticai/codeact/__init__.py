"""
temporal.pydanticai.codeact - A library for building agents with code execution capabilities.

This library combines PydanticAI, Temporal workflows, and Docker sandboxing to create
reliable, long-running AI agents that can execute code safely in isolated environments
with persistent state.

Key Features:
- Persistent State: Variables persist across code executions using pickle serialization
- Sandboxed Security: All code runs in isolated Docker containers with resource limits
- Durable Workflows: Temporal ensures reliable execution with automatic retries
- Type-Safe: Full Pydantic validation for all inputs and outputs
- Flexible Tools: Execute Python, run bash, manage files, and query state
- Dynamic Packages: Install Python and system packages on-demand
- Extensible Design: Easy to create custom agents with specialized capabilities

Quick Start:
    ```python
    from temporal.pydanticai.codeact.agents.simple_agent import SimpleAgent
    from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
    from temporal.pydanticai.codeact.workers.sandbox_worker import CodeActWorkerRunner

    # Build agent
    agent = await SimpleAgent.from_agent_confs(
        agent_builder=AgentBuilder(prompts=prompts, model_configs=configs)
    )

    # Create worker
    worker = await CodeActWorkerRunner.from_args(
        temporal_client=client,
        task_queue='my-queue',
        agents=[agent],
        workflows=[SimpleAgentWorkflow]
    )

    # Run worker
    await worker.run()
    ```

Modules:
- activities: Temporal activity functions for configuration and utilities
- agents: PydanticAI agent implementations (BaseAgent, CodeActAgent, SimpleAgent)
- api: FastAPI application for REST API access
- datamodels: Pydantic models for all data structures
- docker_sandbox: Docker container sandbox implementations
- workflows: Temporal workflow definitions for agent orchestration
- workers: Worker builders for running agents (CodeActWorkerRunner)
"""

__version__ = "0.1.0"

# Core modules
from temporal.pydanticai.codeact import (
    activities,
    agents,
    datamodels,
    docker_sandbox,
    workflows,
    workers,
)
import api

__all__ = [
    "activities",
    "agents",
    "api",
    "datamodels",
    "docker_sandbox",
    "workflows",
    "workers",
]
