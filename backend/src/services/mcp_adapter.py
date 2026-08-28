"""MCP-to-ToolRuntime compatibility adapter.

The adapter intentionally depends on the behavioral MCP client interface
rather than a concrete SDK class, allowing:
- official MCP Python clients,
- compatibility wrappers,
- deterministic unit-test fakes.

MCP schemas are preserved losslessly in ToolDefinition.input_schema and
output_schema. ToolParameter is only a best-effort top-level projection.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Protocol

from services.tool_runtime import (
    ToolDefinition,
    ToolParameter,
    ToolRegistry,
)


class MCPClientLike(Protocol):
    async def list_tools(
        self,
    ) -> Any:
        ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        ...


def _get(
    value: Any,
    name: str,
    default: Any = None,
) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)

    return getattr(
        value,
        name,
        default,
    )


def _plain(
    value: Any,
) -> Any:
    if value is None:
        return None

    if is_dataclass(value):
        return {
            key: _plain(item)
            for key, item
            in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(key): _plain(item)
            for key, item
            in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _plain(item)
            for item in value
        ]

    if hasattr(value, "model_dump"):
        return _plain(
            value.model_dump(
                mode="python"
            )
        )

    if hasattr(value, "__dict__"):
        return {
            str(key): _plain(item)
            for key, item
            in vars(value).items()
            if not str(key).startswith("_")
        }

    return value


def _extract_tools(
    result: Any,
) -> list[Any]:
    tools = _get(
        result,
        "tools",
        None,
    )

    if tools is None:
        if isinstance(result, list):
            return result

        return []

    return list(tools)


def _schema_type(
    schema: Any,
) -> str:
    if not isinstance(schema, dict):
        return "unknown"

    value = schema.get(
        "type",
        "unknown",
    )

    if isinstance(value, list):
        return "|".join(
            str(item)
            for item in value
        )

    return str(value)


def _project_parameters(
    input_schema: dict[str, Any] | None,
) -> list[ToolParameter]:
    """Best-effort top-level projection from JSON Schema."""

    if not isinstance(
        input_schema,
        dict,
    ):
        return []

    properties = input_schema.get(
        "properties",
        {},
    )

    if not isinstance(
        properties,
        dict,
    ):
        return []

    required_raw = input_schema.get(
        "required",
        [],
    )

    required = {
        str(item)
        for item in required_raw
        if isinstance(
            required_raw,
            list,
        )
    }

    result: list[
        ToolParameter
    ] = []

    for name in sorted(
        properties
    ):
        schema = properties[name]

        if not isinstance(
            schema,
            dict,
        ):
            schema = {}

        result.append(
            ToolParameter(
                name=str(name),
                type=_schema_type(
                    schema
                ),
                required=(
                    str(name)
                    in required
                ),
                description=str(
                    schema.get(
                        "description",
                        "",
                    )
                    or ""
                ),
            )
        )

    return result


def mcp_tool_to_definition(
    tool: Any,
    *,
    server_name: str | None = None,
) -> ToolDefinition:
    """Convert one MCP tool description without losing native schema."""

    name = str(
        _get(
            tool,
            "name",
            "",
        )
        or ""
    ).strip()

    if not name:
        raise ValueError(
            "MCP tool name must not be empty"
        )

    input_schema = _plain(
        _get(
            tool,
            "input_schema",
            _get(
                tool,
                "inputSchema",
                None,
            ),
        )
    )

    output_schema = _plain(
        _get(
            tool,
            "output_schema",
            _get(
                tool,
                "outputSchema",
                None,
            ),
        )
    )

    annotations = _plain(
        _get(
            tool,
            "annotations",
            {},
        )
    ) or {}

    read_only = bool(
        _get(
            annotations,
            "readOnlyHint",
            _get(
                annotations,
                "read_only_hint",
                False,
            ),
        )
    )

    return ToolDefinition(
        name=name,
        description=str(
            _get(
                tool,
                "description",
                "",
            )
            or ""
        ),
        parameters=(
            _project_parameters(
                input_schema
            )
        ),
        source="mcp",
        read_only=read_only,
        input_schema=(
            input_schema
            if isinstance(
                input_schema,
                dict,
            )
            else None
        ),
        output_schema=(
            output_schema
            if isinstance(
                output_schema,
                dict,
            )
            else None
        ),
        annotations=(
            annotations
            if isinstance(
                annotations,
                dict,
            )
            else {}
        ),
        metadata={
            "mcp_server_name":
                server_name,
            "mcp_title":
                _get(
                    tool,
                    "title",
                    None,
                ),
        },
    )


def normalize_mcp_call_result(
    result: Any,
) -> dict[str, Any]:
    """Preserve MCP call result as an observation payload."""

    plain = _plain(
        result
    )

    if isinstance(
        plain,
        dict,
    ):
        return plain

    return {
        "content": plain,
    }


class MCPToolAdapter:
    """Register tools exposed by one MCP client into ToolRegistry."""

    def __init__(
        self,
        *,
        client: MCPClientLike,
        server_name: str | None = None,
    ) -> None:
        self.client = client
        self.server_name = (
            server_name
        )

    async def discover(
        self,
    ) -> list[ToolDefinition]:
        result = (
            await self.client.list_tools()
        )

        return [
            mcp_tool_to_definition(
                tool,
                server_name=(
                    self.server_name
                ),
            )
            for tool
            in _extract_tools(result)
        ]

    async def register_tools(
        self,
        registry: ToolRegistry,
    ) -> list[
        ToolDefinition
    ]:
        definitions = (
            await self.discover()
        )

        for definition in definitions:
            tool_name = (
                definition.name
            )

            async def handler(
                arguments: dict[str, Any],
                *,
                _tool_name: str = tool_name,
            ) -> Any:
                result = (
                    await self.client.call_tool(
                        _tool_name,
                        arguments,
                    )
                )

                return normalize_mcp_call_result(
                    result
                )

            registry.register(
                definition=definition,
                handler=handler,
            )

        return definitions
