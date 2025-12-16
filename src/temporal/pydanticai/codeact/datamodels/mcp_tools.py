"""Utilities for extracting and converting MCP server tools to Python function signatures."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Annotated

import pydantic
from pydantic import BaseModel, Field, TypeAdapter
from pydantic_ai import AbstractToolset
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP, MCPServerSSE


class SerializableMCP(BaseModel):
    timeout: float
    read_timeout: float


class SerializedMcpStdio(SerializableMCP):
    kind: Literal['stdio'] = 'stdio'
    command: str
    args: list[str]
    env: Optional[dict[str, str]] = Field(default_factory=dict)
    cwd: Optional[str | Path | None] = Field(default=None)


class SerializedMcpHTTP(SerializableMCP):
    url: str
    headers: Optional[dict[str, str]] = Field(default_factory=dict)


class SerializedMcpStreamableHTTP(SerializedMcpHTTP):
    kind: Literal['streamablehttp'] = 'streamablehttp'


class SerializedMcpSSE(SerializedMcpHTTP):
    kind: Literal['sse'] = 'sse'


ModelSerializedMcp = Annotated[
    SerializedMcpStdio | SerializedMcpStreamableHTTP | SerializedMcpSSE, pydantic.Discriminator('kind')]

ModelSerializedMcpAdapter = TypeAdapter(list[ModelSerializedMcp],
                                        config=pydantic.ConfigDict(defer_build=True, ser_json_bytes='base64',
                                                                   val_json_bytes='base64'))


def serialize_mcp_servers(
        mcp_servers: list[MCPServerStdio | MCPServerStreamableHTTP | MCPServerSSE | AbstractToolset[None]]
) -> list[ModelSerializedMcp]:
    """
    Serialize MCP server configurations to JSON for passing to container.

    Args:
        mcp_servers: List of MCP server configurations

    Returns:
        JSON string containing MCP server configurations
    """
    configs = []

    for server in mcp_servers:
        if isinstance(server, MCPServerStdio):
            # Extract command and args from MCPServerStdio
            command = getattr(server, 'command')
            args = getattr(server, 'args')
            env = getattr(server, 'env', {})
            cwd = getattr(server, 'cwd', None)
            config = {
                'kind': 'stdio',
                'command': command,
                'args': args,
                'env': env,
                'cwd': cwd,
            }
        elif isinstance(server, MCPServerStreamableHTTP):
            url = getattr(server, 'url')
            headers = getattr(server, 'headers')

            config = {
                'kind': 'streamablehttp',
                'url': url,
                'headers': headers,
            }
        elif isinstance(server, MCPServerSSE):
            url = getattr(server, 'url')
            headers = getattr(server, 'headers')
            config = {
                'kind': 'sse',
                'url': url,
                'headers': headers,
            }
        else:
            raise RuntimeError(f"Unsupported server type: {type(server)}")
        timeout = getattr(server, 'timeout')
        read_timeout = getattr(server, 'read_timeout')
        config.update({
            'timeout': timeout,
            'read_timeout': read_timeout,
        })
        configs.append(config)
    return ModelSerializedMcpAdapter.validate_python(configs)
