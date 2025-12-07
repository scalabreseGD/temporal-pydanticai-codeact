"""
Sandbox module containing Docker configuration and Python scripts
for container-based code execution.
"""

from pathlib import Path

# Expose the sandbox directory path for easy access
SANDBOX_DIR = Path(__file__).parent
DOCKERFILE_PATH = SANDBOX_DIR / "Dockerfile.pythonuv"

__all__ = ["SANDBOX_DIR", "DOCKERFILE_PATH"]
