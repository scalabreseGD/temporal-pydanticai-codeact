"""Tests for MCP tool extraction utilities."""

import pytest

from temporal.pydanticai.codeact.datamodels.mcp_tools import (
    extract_mcp_tools_as_functions,
    __format_function_signature,
    __json_schema_type_to_python,
)


class TestJsonSchemaTypeToPython:
    """Test JSON schema to Python type conversion."""

    def test_basic_types(self):
        """Test basic type mappings."""
        assert __json_schema_type_to_python({"type": "string"}) == "str"
        assert __json_schema_type_to_python({"type": "integer"}) == "int"
        assert __json_schema_type_to_python({"type": "number"}) == "float"
        assert __json_schema_type_to_python({"type": "boolean"}) == "bool"
        assert __json_schema_type_to_python({"type": "null"}) == "None"

    def test_optional_types(self):
        """Test optional type handling."""
        assert __json_schema_type_to_python({"type": "string"}, required=False) == "str | None"
        assert __json_schema_type_to_python({"type": "integer"}, required=False) == "int | None"

    def test_array_types(self):
        """Test array type handling."""
        assert __json_schema_type_to_python({"type": "array", "items": {"type": "string"}}) == "list[str]"
        assert __json_schema_type_to_python({"type": "array", "items": {"type": "integer"}}) == "list[int]"
        assert (
                __json_schema_type_to_python({"type": "array", "items": {"type": "string"}}, required=False)
                == "list[str] | None"
        )

    def test_object_types(self):
        """Test object type handling."""
        assert __json_schema_type_to_python({"type": "object"}) == "dict[str, Any]"
        assert (
                __json_schema_type_to_python({"type": "object", "additionalProperties": {"type": "string"}})
                == "dict[str, str]"
        )
        assert (
                __json_schema_type_to_python({"type": "object"}, required=False) == "dict[str, Any] | None"
        )

    def test_enum_types(self):
        """Test enum type handling."""
        result = __json_schema_type_to_python({"type": "string", "enum": ["GET", "POST", "PUT"]})
        assert result == "Literal['GET' | 'POST' | 'PUT']"

    def test_union_types(self):
        """Test anyOf/oneOf union handling."""
        schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        assert __json_schema_type_to_python(schema) == "str | int"

        schema = {"oneOf": [{"type": "boolean"}, {"type": "null"}]}
        assert __json_schema_type_to_python(schema) == "bool | None"

    def test_ref_types(self):
        """Test $ref type handling in arrays."""
        schema = {"type": "array", "items": {"$ref": "#/definitions/MyType"}}
        assert __json_schema_type_to_python(schema) == "list[MyType]"


class TestFormatFunctionSignature:
    """Test function signature formatting."""

    def test_simple_function(self):
        """Test simple function with one parameter."""
        signature = __format_function_signature(
            name="greet",
            description="Greet a person",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )

        assert "def greet(name: str) -> Any:" in signature
        assert '"""Greet a person"""' in signature

    def test_function_with_optional_params(self):
        """Test function with optional parameters."""
        signature = __format_function_signature(
            name="fetch",
            description="Fetch a URL",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["url"],
            },
        )

        assert "def fetch(url: str, timeout: int | None = None) -> Any:" in signature
        assert '"""Fetch a URL"""' in signature

    def test_function_with_multiple_params(self):
        """Test function with multiple required and optional parameters."""
        signature = __format_function_signature(
            name="search",
            description="Search for items",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                    "include_metadata": {"type": "boolean"},
                },
                "required": ["query", "limit"],
            },
        )

        assert "query: str" in signature
        assert "limit: int" in signature
        assert "offset: int | None = None" in signature
        assert "include_metadata: bool | None = None" in signature
        assert '"""Search for items"""' in signature

    def test_function_without_description(self):
        """Test function signature without description."""
        signature = __format_function_signature(
            name="simple",
            description=None,
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        )

        assert "def simple(value: str) -> Any:" in signature
        assert '"""' not in signature

    def test_function_with_complex_types(self):
        """Test function with complex parameter types."""
        signature = __format_function_signature(
            name="process",
            description="Process data",
            input_schema={
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}},
                    "config": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "required": ["items"],
            },
        )

        assert "items: list[str]" in signature
        assert "config: dict[str, str] | None = None" in signature


@pytest.mark.integration
class TestExtractMCPToolsAsFunctions:
    """Integration tests for extracting tools from MCP servers."""

    @pytest.mark.skip(reason="Requires running MCP server")
    async def test_extract_from_stdio_server(self):
        """Test extracting tools from a stdio MCP server."""
        from pydantic_ai.mcp import MCPServerStdio

        # This test requires mcp-server-fetch to be available
        server = MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-fetch"])

        functions = await extract_mcp_tools_as_functions(server)

        assert len(functions) > 0
        assert any("def fetch" in func for func in functions)

    def test_extract_from_mock_server(self):
        """Test with a mock server to verify the extraction logic."""
        # This is a placeholder for a unit test with a mocked server
        # In practice, you would mock the server.list_tools() method
        pass


class TestEndToEnd:
    """End-to-end tests demonstrating usage."""

    def test_example_output_format(self):
        """Test that the output format matches the expected structure."""
        signature = __format_function_signature(
            name="calculate_sum",
            description="Calculate the sum of two numbers",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        )

        expected_lines = [
            "def calculate_sum(a: float, b: float) -> Any:",
            '"""Calculate the sum of two numbers"""',
        ]

        for line in expected_lines:
            assert line in signature
