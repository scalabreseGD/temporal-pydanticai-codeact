"""Utilities for extracting and converting MCP server tools to Python function signatures."""

from __future__ import annotations

from typing import Any, Union

from pydantic_ai import AbstractToolset
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, MCPServerStreamableHTTP


def __json_schema_type_to_python(
    schema: dict[str, Any], required: bool = True
) -> str:
    """Convert a JSON schema type to Python type annotation string.

    Args:
        schema: JSON schema definition for a parameter
        required: Whether the parameter is required

    Returns:
        Python type annotation as a string
    """
    # Handle anyOf/oneOf unions first (before checking type field)
    if "anyOf" in schema or "oneOf" in schema:
        variants = schema.get("anyOf") or schema.get("oneOf", [])
        types = [__json_schema_type_to_python(v, required=True) for v in variants]
        base_type = " | ".join(types)
        return base_type if required else f"{base_type} | None"

    # Handle enum types
    if "enum" in schema:
        enum_values = schema["enum"]
        # Create a union of literal types
        literals = " | ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in enum_values])
        base_type = f"Literal[{literals}]"
        return base_type if required else f"{base_type} | None"

    json_type = schema.get("type")

    # Handle None/null type
    if json_type is None or json_type == "null":
        return "None"

    # Handle array/list types with $ref
    if json_type == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            ref_name = items["$ref"].split("/")[-1]
            base_type = f"list[{ref_name}]"
        else:
            item_type = __json_schema_type_to_python(items, required=True)
            base_type = f"list[{item_type}]"
        return base_type if required else f"{base_type} | None"

    # Handle object types
    if json_type == "object":
        # For complex objects, use dict as a fallback
        additional = schema.get("additionalProperties")
        if additional:
            value_type = __json_schema_type_to_python(additional, required=True) if isinstance(additional, dict) else "Any"
            base_type = f"dict[str, {value_type}]"
        else:
            base_type = "dict[str, Any]"
        return base_type if required else f"{base_type} | None"

    # Basic type mapping
    type_map = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "null": "None",
    }

    base_type = type_map.get(json_type, "Any")
    return base_type if required else f"{base_type} | None"


def __format_function_signature(
    name: str, description: str | None, input_schema: dict[str, Any]
) -> str:
    """Convert MCP tool metadata to a Python function signature string.

    Args:
        name: The name of the tool/function
        description: Optional description of what the tool does
        input_schema: JSON schema defining the tool's input parameters

    Returns:
        A formatted Python function signature as a string
    """
    # Extract parameters from the schema
    properties = input_schema.get("properties", {})
    required_params = set(input_schema.get("required", []))

    # Build parameter list
    params = []
    for param_name, param_schema in properties.items():
        is_required = param_name in required_params
        param_type = __json_schema_type_to_python(param_schema, required=is_required)

        # Format parameter with type annotation
        if is_required:
            params.append(f"{param_name}: {param_type}")
        else:
            params.append(f"{param_name}: {param_type} = None")

    # Join parameters
    params_str = ", ".join(params)

    # Format the function signature
    signature = f"def {name}({params_str}) -> Any:"

    # Add docstring if description is provided
    if description:
        # Clean up the description - escape quotes and handle multi-line
        clean_desc = description.replace('"""', r"\"\"\"").strip()
        signature += f'\n    """{clean_desc}"""'

    return signature


async def extract_mcp_tools_as_functions(
    server: AbstractToolset,
) -> list[str]:
    """Extract tools from an MCP server and return them as Python function signatures.

    Args:
        server: An instance of MCPServerStdio, MCPServerStreamableHTTP, or MCPServerSSE

    Returns:
        A list of Python function signature strings

    Example:
        >>> server = MCPServerStdio("uv", ["run", "mcp-server-fetch"])
        >>> functions = await extract_mcp_tools_as_functions(server)
        >>> for func in functions:
        ...     print(func)
        def fetch(url: str, max_length: int | None = None) -> Any:
            \"\"\"Fetches a URL from the internet and optionally extracts its contents as markdown.\"\"\"
    """
    # List all tools from the server (this automatically enters/exits the server context)
    tools = await server.list_tools()

    # Convert each tool to a function signature
    function_signatures = []
    for tool in tools:
        signature = __format_function_signature(
            name=tool.name,
            description=tool.description,
            input_schema=tool.inputSchema,
        )
        function_signatures.append(signature)

    return function_signatures
