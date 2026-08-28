import asyncio

from services.search_tool_adapter import (
    SearchToolAdapter,
    build_search_tool_definition,
)
from services.tool_runtime import (
    TOOL_EXECUTION_ERROR,
    TOOL_SUCCESS,
    ToolInvocation,
    ToolRegistry,
)


def test_search_definition_is_read_only():
    definition = (
        build_search_tool_definition()
    )

    assert (
        definition.name
        == "web_search"
    )

    assert (
        definition.source
        == "search"
    )

    assert (
        definition.read_only
        is True
    )


def test_search_definition_preserves_schema():
    definition = (
        build_search_tool_definition()
    )

    assert (
        definition.input_schema[
            "type"
        ]
        == "object"
    )

    assert (
        "query"
        in definition.input_schema[
            "required"
        ]
    )


def test_search_adapter_registers_runtime_tool():
    registry = ToolRegistry()

    adapter = SearchToolAdapter(
        search=lambda query, limit: [],
    )

    definition = adapter.register(
        registry
    )

    assert (
        definition.name
        == "web_search"
    )

    assert (
        registry.get(
            "web_search"
        )
        is not None
    )


def test_search_tool_invokes_existing_sync_backend():
    calls = []

    def search(
        query,
        limit,
    ):
        calls.append(
            (query, limit)
        )

        return [
            {
                "title": "Result",
            }
        ]

    async def run():
        registry = ToolRegistry()

        SearchToolAdapter(
            search=search,
        ).register(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="web_search",
                    arguments={
                        "query": "agent runtime",
                        "max_results": 3,
                    },
                )
            )
        )

        assert (
            result.status
            == TOOL_SUCCESS
        )

        assert calls == [
            (
                "agent runtime",
                3,
            )
        ]

        assert result.output == [
            {
                "title": "Result",
            }
        ]

    asyncio.run(run())


def test_search_tool_supports_async_backend():
    calls = []

    async def search(
        query,
        limit,
    ):
        calls.append(
            (query, limit)
        )

        return ["async-result"]

    async def run():
        registry = ToolRegistry()

        SearchToolAdapter(
            search=search,
        ).register(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="web_search",
                    arguments={
                        "query": "MCP",
                    },
                )
            )
        )

        assert (
            result.status
            == TOOL_SUCCESS
        )

        assert (
            result.output
            == ["async-result"]
        )

        assert calls == [
            ("MCP", 5)
        ]

    asyncio.run(run())


def test_search_tool_uses_default_result_limit():
    calls = []

    def search(
        query,
        limit,
    ):
        calls.append(limit)
        return []

    async def run():
        registry = ToolRegistry()

        SearchToolAdapter(
            search=search,
            default_max_results=7,
        ).register(
            registry
        )

        await registry.invoke_async(
            ToolInvocation(
                tool_name="web_search",
                arguments={
                    "query": "test",
                },
            )
        )

    asyncio.run(run())

    assert calls == [7]


def test_empty_search_query_is_structured_failure():
    async def run():
        registry = ToolRegistry()

        SearchToolAdapter(
            search=lambda query, limit: [],
        ).register(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="web_search",
                    arguments={
                        "query": "   ",
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
            == "ValueError"
        )

    asyncio.run(run())


def test_search_provider_failure_is_structured():
    def search(
        query,
        limit,
    ):
        raise RuntimeError(
            "search provider unavailable"
        )

    async def run():
        registry = ToolRegistry()

        SearchToolAdapter(
            search=search,
        ).register(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="web_search",
                    arguments={
                        "query": "test",
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
            == "search provider unavailable"
        )

    asyncio.run(run())


def test_search_tool_trace_identifies_source():
    async def run():
        registry = ToolRegistry()

        SearchToolAdapter(
            search=lambda query, limit: [],
            source="tavily",
        ).register(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="web_search",
                    arguments={
                        "query": "test",
                    },
                )
            )
        )

        assert result.trace is not None

        assert (
            result.trace.tool_source
            == "tavily"
        )

        assert (
            result.trace.duration_ms
            >= 0
        )

    asyncio.run(run())


def test_search_tool_does_not_create_decision_truth():
    async def run():
        registry = ToolRegistry()

        SearchToolAdapter(
            search=lambda query, limit: [
                {
                    "text": (
                        "Candidate A is best"
                    )
                }
            ],
        ).register(
            registry
        )

        result = (
            await registry.invoke_async(
                ToolInvocation(
                    tool_name="web_search",
                    arguments={
                        "query": "test",
                    },
                )
            )
        )

        forbidden = {
            "candidate_score",
            "recommendation",
            "readiness",
            "decision_truth",
        }

        assert not (
            forbidden
            & set(vars(result))
        )

    asyncio.run(run())
