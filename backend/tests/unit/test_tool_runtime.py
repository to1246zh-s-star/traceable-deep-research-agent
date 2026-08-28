from services.tool_runtime import (
    TOOL_EXECUTION_ERROR,
    TOOL_INVALID_ARGUMENTS,
    TOOL_NOT_FOUND,
    TOOL_SUCCESS,
    ToolDefinition,
    ToolInvocation,
    ToolParameter,
    ToolRegistry,
)


def test_register_and_list_tools():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="search",
            description="Search docs",
        ),
        handler=lambda args: [],
    )

    tools = registry.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "search"


def test_tool_names_are_listed_deterministically():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="z_tool",
            description="z",
        ),
        handler=lambda args: None,
    )

    registry.register(
        definition=ToolDefinition(
            name="a_tool",
            description="a",
        ),
        handler=lambda args: None,
    )

    assert [
        tool.name
        for tool in registry.list_tools()
    ] == [
        "a_tool",
        "z_tool",
    ]


def test_duplicate_tool_name_rejected():
    registry = ToolRegistry()

    definition = ToolDefinition(
        name="search",
        description="Search",
    )

    registry.register(
        definition=definition,
        handler=lambda args: None,
    )

    try:
        registry.register(
            definition=ToolDefinition(
                name="search",
                description="Other",
            ),
            handler=lambda args: None,
        )
    except ValueError as exc:
        assert (
            "already registered"
            in str(exc)
        )
    else:
        raise AssertionError(
            "duplicate registration allowed"
        )


def test_unknown_tool_returns_structured_failure():
    registry = ToolRegistry()

    result = registry.invoke(
        ToolInvocation(
            tool_name="missing",
        )
    )

    assert (
        result.status
        == TOOL_NOT_FOUND
    )

    assert (
        result.error_type
        == "tool_not_found"
    )

    assert result.succeeded is False


def test_required_argument_is_validated():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="search",
            description="Search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    required=True,
                )
            ],
        ),
        handler=lambda args: args,
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="search",
            arguments={},
        )
    )

    assert (
        result.status
        == TOOL_INVALID_ARGUMENTS
    )

    assert (
        "query"
        in result.error_message
    )


def test_unknown_argument_is_rejected():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="search",
            description="Search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                )
            ],
        ),
        handler=lambda args: args,
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="search",
            arguments={
                "query": "abc",
                "unexpected": True,
            },
        )
    )

    assert (
        result.status
        == TOOL_INVALID_ARGUMENTS
    )

    assert (
        "unexpected"
        in result.error_message
    )


def test_successful_invocation_returns_output():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="echo",
            description="Echo",
            parameters=[
                ToolParameter(
                    name="value",
                    type="string",
                )
            ],
        ),
        handler=lambda args: {
            "echo": args["value"]
        },
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="echo",
            arguments={
                "value": "hello",
            },
        )
    )

    assert (
        result.status
        == TOOL_SUCCESS
    )

    assert result.succeeded is True

    assert result.output == {
        "echo": "hello",
    }


def test_handler_exception_is_structured():
    registry = ToolRegistry()

    def failing_handler(
        args,
    ):
        raise RuntimeError(
            "provider failed"
        )

    registry.register(
        definition=ToolDefinition(
            name="failure",
            description="Fail",
        ),
        handler=failing_handler,
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="failure",
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
        == "provider failed"
    )


def test_handler_receives_argument_copy():
    registry = ToolRegistry()

    captured = {}

    def handler(
        args,
    ):
        args["mutated"] = True
        captured.update(args)
        return "ok"

    registry.register(
        definition=ToolDefinition(
            name="tool",
            description="Tool",
            parameters=[
                ToolParameter(
                    name="value",
                    type="string",
                )
            ],
        ),
        handler=handler,
    )

    original = {
        "value": "x",
    }

    registry.invoke(
        ToolInvocation(
            tool_name="tool",
            arguments=original,
        )
    )

    assert original == {
        "value": "x",
    }

    assert (
        captured["mutated"]
        is True
    )


def test_tool_definition_keeps_runtime_metadata():
    definition = ToolDefinition(
        name="search",
        description="Search docs",
        source="mcp",
        read_only=True,
    )

    assert (
        definition.source
        == "mcp"
    )

    assert (
        definition.read_only
        is True
    )


def test_tool_result_has_no_decision_truth_fields():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="echo",
            description="Echo",
        ),
        handler=lambda args: "ok",
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="echo",
        )
    )

    forbidden = {
        "candidate_score",
        "readiness",
        "recommendation",
        "constraint_result",
        "decision_truth",
    }

    assert not (
        forbidden
        & set(vars(result))
    )


def test_successful_tool_result_contains_execution_trace():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="echo_trace",
            description="Echo",
            source="local",
        ),
        handler=lambda args: "ok",
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="echo_trace",
        )
    )

    assert result.trace is not None

    assert (
        result.trace.tool_name
        == "echo_trace"
    )

    assert (
        result.trace.tool_source
        == "local"
    )

    assert (
        result.trace.status
        == TOOL_SUCCESS
    )

    assert (
        result.trace.duration_ms
        >= 0
    )

    assert (
        result.trace.invocation_id
        .startswith("tool_")
    )


def test_failed_tool_result_contains_error_trace():
    registry = ToolRegistry()

    def fail(args):
        raise RuntimeError("boom")

    registry.register(
        definition=ToolDefinition(
            name="failure_trace",
            description="Failure",
            source="local",
        ),
        handler=fail,
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="failure_trace",
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

    assert (
        result.trace.error_message
        == "boom"
    )


def test_unknown_tool_trace_has_unknown_source():
    registry = ToolRegistry()

    result = registry.invoke(
        ToolInvocation(
            tool_name="missing_trace",
        )
    )

    assert result.trace is not None

    assert (
        result.trace.tool_source
        == "unknown"
    )


def test_trace_argument_copy_is_not_mutated():
    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="argument_trace",
            description="Args",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                )
            ],
        ),
        handler=lambda args: "ok",
    )

    arguments = {
        "query": "hello"
    }

    result = registry.invoke(
        ToolInvocation(
            tool_name="argument_trace",
            arguments=arguments,
        )
    )

    arguments["query"] = "changed"

    assert (
        result.trace.arguments["query"]
        == "hello"
    )


def test_persisted_tool_trace_excludes_arguments():
    from services.tool_runtime import (
        serialize_tool_trace_for_persistence,
    )

    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="sensitive_tool",
            description="Sensitive",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                )
            ],
        ),
        handler=lambda args: "ok",
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="sensitive_tool",
            arguments={
                "query": "private internal query",
            },
        )
    )

    persisted = (
        serialize_tool_trace_for_persistence(
            result.trace
        )
    )

    assert persisted is not None
    assert "arguments" not in persisted
    assert "output" not in persisted

    assert (
        persisted["tool_name"]
        == "sensitive_tool"
    )


def test_persisted_tool_trace_is_observability_only():
    from services.tool_runtime import (
        serialize_tool_trace_for_persistence,
    )

    registry = ToolRegistry()

    registry.register(
        definition=ToolDefinition(
            name="decision_sounding_tool",
            description="Observation",
        ),
        handler=lambda args: (
            "Candidate A should win"
        ),
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="decision_sounding_tool",
        )
    )

    persisted = (
        serialize_tool_trace_for_persistence(
            result.trace
        )
    )

    forbidden = {
        "recommendation",
        "candidate_score",
        "readiness",
        "decision_truth",
        "output",
    }

    assert not (
        forbidden
        & set(persisted)
    )


def test_execution_error_preserves_runtime_exception_object():
    registry = ToolRegistry()

    error = TimeoutError(
        "provider timeout"
    )

    def fail(args):
        raise error

    registry.register(
        definition=ToolDefinition(
            name="timeout_tool",
            description="Timeout",
        ),
        handler=fail,
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="timeout_tool",
        )
    )

    assert (
        result.status
        == TOOL_EXECUTION_ERROR
    )

    assert result.exception is error

    assert (
        result.error_type
        == "TimeoutError"
    )


def test_persisted_trace_excludes_runtime_exception():
    from services.tool_runtime import (
        serialize_tool_trace_for_persistence,
    )

    registry = ToolRegistry()

    def fail(args):
        raise TimeoutError(
            "secret timeout context"
        )

    registry.register(
        definition=ToolDefinition(
            name="timeout_safe",
            description="Timeout",
        ),
        handler=fail,
    )

    result = registry.invoke(
        ToolInvocation(
            tool_name="timeout_safe",
        )
    )

    persisted = (
        serialize_tool_trace_for_persistence(
            result.trace
        )
    )

    assert persisted is not None

    assert (
        "exception"
        not in persisted
    )

    assert (
        persisted["error_type"]
        == "TimeoutError"
    )
