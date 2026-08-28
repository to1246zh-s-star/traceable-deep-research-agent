import asyncio
from types import SimpleNamespace

import pytest

from services.mcp_adapter import (
    MCPToolAdapter,
    mcp_tool_to_definition,
    normalize_mcp_call_result,
)
from services.tool_runtime import (
    TOOL_EXECUTION_ERROR,
    TOOL_SUCCESS,
    ToolInvocation,
    ToolRegistry,
)


class FakeMCPClient:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="search_docs",
                    title="Search Docs",
                    description="Search documentation",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": (
                                    "Search query"
                                ),
                            },
                            "limit": {
                                "type": "integer",
                            },
                        },
                        "required": [
                            "query",
                        ],
                    },
                    output_schema={
                        "type": "object",
                    },
                    annotations={
                        "readOnlyHint": True,
                    },
                )
            ]
        )

    async def call_tool(
        self,
        name,
        arguments,
    ):
        self.calls.append(
            (
                name,
                dict(arguments),
            )
        )

        return SimpleNamespace(
            content=[
                {
                    "type": "text",
                    "text": "result",
                }
            ],
            isError=False,
        )


def test_mcp_definition_preserves_full_input_schema():
    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
            }
        },
        "required": ["query"],
        "oneOf": [
            {
                "required": [
                    "query"
                ]
            }
        ],
    }

    tool = SimpleNamespace(
        name="search",
        description="Search",
        input_schema=schema,
        output_schema=None,
        annotations={},
    )

    definition = (
        mcp_tool_to_definition(
            tool
        )
    )

    assert (
        definition.input_schema
        == schema
    )

    assert (
        "oneOf"
        in definition.input_schema
    )


def test_mcp_parameters_are_best_effort_projection():
    tool = SimpleNamespace(
        name="search",
        description="Search",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                },
                "query": {
                    "type": "string",
                },
            },
            "required": [
                "query",
            ],
        },
        annotations={},
    )

    definition = (
        mcp_tool_to_definition(
            tool
        )
    )

    assert [
        item.name
        for item
        in definition.parameters
    ] == [
        "limit",
        "query",
    ]

    parameter_map = {
        item.name: item
        for item
        in definition.parameters
    }

    assert (
        parameter_map[
            "query"
        ].required
        is True
    )

    assert (
        parameter_map[
            "limit"
        ].required
        is False
    )


def test_mcp_definition_marks_source():
    tool = SimpleNamespace(
        name="search",
        description="Search",
        input_schema={
            "type": "object",
        },
        annotations={},
    )

    definition = (
        mcp_tool_to_definition(
            tool,
            server_name="docs",
        )
    )

    assert (
        definition.source
        == "mcp"
    )

    assert (
        definition.metadata[
            "mcp_server_name"
        ]
        == "docs"
    )


def test_mcp_read_only_annotation_preserved():
    tool = SimpleNamespace(
        name="read",
        description="Read",
        input_schema={
            "type": "object",
        },
        annotations={
            "readOnlyHint": True,
        },
    )

    definition = (
        mcp_tool_to_definition(
            tool
        )
    )

    assert (
        definition.read_only
        is True
    )


def test_adapter_discovers_tools():
    async def run():
        client = FakeMCPClient()

        adapter = MCPToolAdapter(
            client=client,
            server_name="docs",
        )

        tools = await adapter.discover()

        assert len(tools) == 1

        assert (
            tools[0].name
            == "search_docs"
        )

    asyncio.run(run())


def test_adapter_registers_and_invokes_mcp_tool():
    async def run():
        client = FakeMCPClient()

        registry = ToolRegistry()

        adapter = MCPToolAdapter(
            client=client,
            server_name="docs",
        )

        await adapter.register_tools(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="search_docs",
                    arguments={
                        "query": "MCP",
                        "limit": 5,
                    },
                )
            )
        )

        assert (
            result.status
            == TOOL_SUCCESS
        )

        assert client.calls == [
            (
                "search_docs",
                {
                    "query": "MCP",
                    "limit": 5,
                },
            )
        ]

        assert (
            result.output["isError"]
            is False
        )

    asyncio.run(run())


def test_sync_tool_still_works_through_async_runtime():
    async def run():
        registry = ToolRegistry()

        from services.tool_runtime import (
            ToolDefinition,
        )

        registry.register(
            definition=ToolDefinition(
                name="local",
                description="Local",
            ),
            handler=lambda args: "ok",
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="local",
                )
            )
        )

        assert (
            result.status
            == TOOL_SUCCESS
        )

        assert result.output == "ok"

    asyncio.run(run())


def test_mcp_client_exception_becomes_structured_tool_failure():
    async def run():
        class FailingClient(
            FakeMCPClient
        ):
            async def call_tool(
                self,
                name,
                arguments,
            ):
                raise RuntimeError(
                    "MCP unavailable"
                )

        client = FailingClient()

        registry = ToolRegistry()

        adapter = MCPToolAdapter(
            client=client,
        )

        await adapter.register_tools(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="search_docs",
                    arguments={
                        "query": "x",
                    },
                )
            )
        )

        assert (
            result.status
            == TOOL_EXECUTION_ERROR
        )

        assert (
            result.error_type
            == "RuntimeError"
        )

        assert (
            result.error_message
            == "MCP unavailable"
        )

    asyncio.run(run())


def test_normalize_mcp_result_does_not_infer_decision_truth():
    result = SimpleNamespace(
        content=[
            {
                "type": "text",
                "text": "candidate A wins",
            }
        ],
        isError=False,
    )

    normalized = (
        normalize_mcp_call_result(
            result
        )
    )

    forbidden = {
        "candidate_score",
        "readiness",
        "recommendation",
        "decision_truth",
    }

    assert not (
        forbidden
        & set(normalized)
    )


def test_complex_schema_is_not_flattened_lossily():
    schema = {
        "type": "object",
        "$defs": {
            "filter": {
                "type": "object",
            }
        },
        "properties": {
            "query": {
                "type": "string",
            }
        },
        "anyOf": [
            {
                "required": [
                    "query"
                ]
            }
        ],
    }

    tool = SimpleNamespace(
        name="complex",
        description="Complex",
        input_schema=schema,
        annotations={},
    )

    definition = (
        mcp_tool_to_definition(
            tool
        )
    )

    assert (
        definition.input_schema[
            "$defs"
        ]
        == schema["$defs"]
    )

    assert (
        definition.input_schema[
            "anyOf"
        ]
        == schema["anyOf"]
    )


def test_mcp_tool_uses_unified_execution_trace():
    async def run():
        client = FakeMCPClient()

        registry = ToolRegistry()

        adapter = MCPToolAdapter(
            client=client,
            server_name="docs",
        )

        await adapter.register_tools(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="search_docs",
                    arguments={
                        "query": "trace",
                    },
                )
            )
        )

        assert result.trace is not None

        assert (
            result.trace.tool_source
            == "mcp"
        )

        assert (
            result.trace.status
            == TOOL_SUCCESS
        )

    asyncio.run(run())


def test_mcp_failure_trace_preserves_runtime_error():
    async def run():
        class FailingClient(
            FakeMCPClient
        ):
            async def call_tool(
                self,
                name,
                arguments,
            ):
                raise RuntimeError(
                    "transport failed"
                )

        registry = ToolRegistry()

        adapter = MCPToolAdapter(
            client=FailingClient(),
            server_name="docs",
        )

        await adapter.register_tools(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="search_docs",
                    arguments={
                        "query": "x",
                    },
                )
            )
        )

        assert result.trace is not None

        assert (
            result.trace.status
            == TOOL_EXECUTION_ERROR
        )

        assert (
            result.trace.error_type
            == "RuntimeError"
        )

    asyncio.run(run())
