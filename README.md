# Code Act PydanticAI

Building agents with code execution capabilities using PydanticAI, Temporal, and Docker.

## Overview

This project combines three powerful technologies to create intelligent agents that can execute code safely:

- **PydanticAI**: Agent framework for building type-safe AI applications
- **Temporal**: Workflow orchestration for reliable, long-running processes
- **Docker**: Containerized code execution for security and isolation

## Project Structure

```
code-act-pydanticai/
├── src/
│   ├── __init__.py
│   └── docker_sandbox/       # Secure code execution in Docker containers
│       └── __init__.py
├── tests/
│   └── __init__.py
├── docs/
├── pyproject.toml
└── README.md
```

## Installation

### Prerequisites

- Python 3.13+
- Docker (for containerized code execution)
- uv (package manager)

### Setup

1. Clone the repository
2. Install dependencies:

```bash
uv sync
```

For development dependencies:

```bash
uv sync --extra dev
```

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy src/
```

### Linting

```bash
ruff check .
```

## License

TBD
