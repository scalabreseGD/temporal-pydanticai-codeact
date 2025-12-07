# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project named **code-act-pydanticai**, focused on building agents with code execution capabilities using:
- **PydanticAI** (v1.27.0) - Anthropic's agent framework for building production-grade GenAI applications
- **Temporal** (v1.19.0) - Workflow orchestration for reliable, long-running processes
- **Docker Python Client** (v7.1.0) - Programmatic Docker container management

## Environment Setup

- **Python Version**: 3.13+
- **Virtual Environment**: `.venv/` (already configured)
- **Package Manager**: uv (inferred from pyproject.toml structure)

## Core Dependencies

- **pydantic-ai** (>=1.27.0): Agent framework for building type-safe AI applications
- **temporalio** (>=1.19.0): Workflow orchestration and durable execution
- **docker** (>=7.1.0): Docker Engine API client for container management

## Documentation Requirements

**CRITICAL**: Before writing any code that uses external libraries or frameworks, you MUST check Context7 MCP for the most up-to-date documentation. Use the `mcp__context7__resolve-library-id` and `mcp__context7__get-library-docs` tools to retrieve current API references and code examples.

This is especially important for:
- PydanticAI API usage and patterns
- Python standard library updates (since this uses Python 3.13+)
- Any third-party dependencies added to the project

## Common Commands

### Environment Management
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (when added to pyproject.toml)
uv sync

# Add new dependencies
uv add <package-name>
```

### Development Workflow
```bash
# Run tests (when test suite is added)
pytest

# Run a single test file
pytest tests/test_<filename>.py

# Run with verbose output
pytest -v

# Type checking (when mypy is added)
mypy .

# Linting (when ruff is added)
ruff check .

# Auto-fix linting issues
ruff check --fix .
```

## Architecture Notes

**Current State**: This is a newly initialized project with minimal structure. As the codebase develops, this section should be updated with:

- Core agent architecture and how PydanticAI is integrated
- Key modules and their responsibilities
- Data flow patterns
- Integration points with external services or APIs