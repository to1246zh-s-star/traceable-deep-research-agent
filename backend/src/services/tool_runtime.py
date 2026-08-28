"""Deterministic tool runtime primitives.

This module provides a small production-style abstraction for Agent tools.

Important semantics:
- tool identity is explicit and unique;
- schemas are explicit metadata;
- invocation failures are represented structurally;
- one tool failure does not crash the registry;
- tools return observations, not decision truth;
- no LLM dependency is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from inspect import isawaitable
from time import perf_counter
from uuid import uuid4
from typing import Any, Awaitable, Callable


TOOL_SUCCESS = "SUCCESS"
TOOL_NOT_FOUND = "NOT_FOUND"
TOOL_INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
TOOL_EXECUTION_ERROR = "EXECUTION_ERROR"


@dataclass(kw_only=True)
class ToolParameter:
    """One declared tool input parameter."""

    name: str
    type: str
    required: bool = True
    description: str = ""


@dataclass(kw_only=True)
class ToolDefinition:
    """Static tool metadata exposed to the Agent runtime."""

    name: str
    description: str

    parameters: list[ToolParameter] = field(
        default_factory=list
    )

    source: str = "local"

    read_only: bool = True

    # Preserve protocol-native schemas losslessly.
    # `parameters` remains a convenient flat view for simple tools.
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    annotations: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # Preserve protocol-native schemas losslessly.
    # `parameters` remains a convenient flat view for simple tools.
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    annotations: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(kw_only=True)
class ToolInvocation:
    """One requested tool call."""

    tool_name: str

    arguments: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(kw_only=True)
class ToolExecutionTrace:
    """Runtime observability for one tool invocation."""

    invocation_id: str
    tool_name: str
    tool_source: str

    status: str

    duration_ms: float = 0.0

    error_type: str | None = None
    error_message: str | None = None

    arguments: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(kw_only=True)
class ToolResult:
    """Structured result of one tool invocation."""

    tool_name: str
    status: str

    output: Any = None

    error_type: str | None = None
    error_message: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    trace: ToolExecutionTrace | None = None

    # Runtime-only original exception. This is intentionally excluded
    # from persisted trace serialization.
    exception: Exception | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @property
    def succeeded(self) -> bool:
        return (
            self.status
            == TOOL_SUCCESS
        )


@dataclass(kw_only=True)
class RegisteredTool:
    """Runtime binding between metadata and implementation."""

    definition: ToolDefinition

    handler: Callable[
        [dict[str, Any]],
        Any | Awaitable[Any],
    ]


class ToolRegistry:
    """Deterministic registry and invocation boundary."""

    def __init__(self) -> None:
        self._tools: dict[
            str,
            RegisteredTool
        ] = {}

    def register(
        self,
        *,
        definition: ToolDefinition,
        handler: Callable[
            [dict[str, Any]],
            Any | Awaitable[Any],
        ],
    ) -> None:
        name = definition.name.strip()

        if not name:
            raise ValueError(
                "Tool name must not be empty"
            )

        if name in self._tools:
            raise ValueError(
                f"Tool already registered: {name}"
            )

        definition.name = name

        self._tools[name] = (
            RegisteredTool(
                definition=definition,
                handler=handler,
            )
        )

    def list_tools(
        self,
    ) -> list[ToolDefinition]:
        return [
            self._tools[name].definition
            for name in sorted(
                self._tools
            )
        ]

    def get(
        self,
        name: str,
    ) -> RegisteredTool | None:
        return self._tools.get(
            name
        )

    def invoke(
        self,
        invocation: ToolInvocation,
    ) -> ToolResult:
        invocation_id = (
            f"tool_{uuid4().hex[:12]}"
        )

        started_at = perf_counter()

        registered = self.get(
            invocation.tool_name
        )

        if registered is None:
            status = TOOL_NOT_FOUND
            error_type = "tool_not_found"
            error_message = (
                "Tool is not registered"
            )

            return ToolResult(
                tool_name=invocation.tool_name,
                status=status,
                error_type=error_type,
                error_message=error_message,
                trace=_build_trace(
                    invocation_id=invocation_id,
                    invocation=invocation,
                    definition=None,
                    status=status,
                    started_at=started_at,
                    error_type=error_type,
                    error_message=error_message,
                ),
            )

        definition = (
            registered.definition
        )

        validation_error = (
            _validate_arguments(
                definition,
                invocation.arguments,
            )
        )

        if validation_error is not None:
            status = TOOL_INVALID_ARGUMENTS
            error_type = (
                "invalid_arguments"
            )

            return ToolResult(
                tool_name=invocation.tool_name,
                status=status,
                error_type=error_type,
                error_message=validation_error,
                trace=_build_trace(
                    invocation_id=invocation_id,
                    invocation=invocation,
                    definition=definition,
                    status=status,
                    started_at=started_at,
                    error_type=error_type,
                    error_message=validation_error,
                ),
            )

        try:
            output = registered.handler(
                dict(invocation.arguments)
            )

            if isawaitable(output):
                raise RuntimeError(
                    "Async tool requires invoke_async()"
                )

        except Exception as exc:
            status = TOOL_EXECUTION_ERROR
            error_type = type(exc).__name__
            error_message = str(exc)

            return ToolResult(
                tool_name=invocation.tool_name,
                status=status,
                error_type=error_type,
                error_message=error_message,
                trace=_build_trace(
                    invocation_id=invocation_id,
                    invocation=invocation,
                    definition=definition,
                    status=status,
                    started_at=started_at,
                    error_type=error_type,
                    error_message=error_message,
                ),
                exception=exc,
            )

        status = TOOL_SUCCESS

        return ToolResult(
            tool_name=invocation.tool_name,
            status=status,
            output=output,
            trace=_build_trace(
                invocation_id=invocation_id,
                invocation=invocation,
                definition=definition,
                status=status,
                started_at=started_at,
            ),
        )

    async def invoke_async(
        self,
        invocation: ToolInvocation,
    ) -> ToolResult:
        """Invoke either a synchronous or asynchronous tool."""

        invocation_id = (
            f"tool_{uuid4().hex[:12]}"
        )

        started_at = perf_counter()

        registered = self.get(
            invocation.tool_name
        )

        if registered is None:
            status = TOOL_NOT_FOUND
            error_type = "tool_not_found"
            error_message = (
                "Tool is not registered"
            )

            return ToolResult(
                tool_name=invocation.tool_name,
                status=status,
                error_type=error_type,
                error_message=error_message,
                trace=_build_trace(
                    invocation_id=invocation_id,
                    invocation=invocation,
                    definition=None,
                    status=status,
                    started_at=started_at,
                    error_type=error_type,
                    error_message=error_message,
                ),
            )

        definition = (
            registered.definition
        )

        validation_error = (
            _validate_arguments(
                definition,
                invocation.arguments,
            )
        )

        if validation_error is not None:
            status = TOOL_INVALID_ARGUMENTS
            error_type = (
                "invalid_arguments"
            )

            return ToolResult(
                tool_name=invocation.tool_name,
                status=status,
                error_type=error_type,
                error_message=validation_error,
                trace=_build_trace(
                    invocation_id=invocation_id,
                    invocation=invocation,
                    definition=definition,
                    status=status,
                    started_at=started_at,
                    error_type=error_type,
                    error_message=validation_error,
                ),
            )

        try:
            output = registered.handler(
                dict(invocation.arguments)
            )

            if isawaitable(output):
                output = await output

        except Exception as exc:
            status = TOOL_EXECUTION_ERROR
            error_type = type(exc).__name__
            error_message = str(exc)

            return ToolResult(
                tool_name=invocation.tool_name,
                status=status,
                error_type=error_type,
                error_message=error_message,
                trace=_build_trace(
                    invocation_id=invocation_id,
                    invocation=invocation,
                    definition=definition,
                    status=status,
                    started_at=started_at,
                    error_type=error_type,
                    error_message=error_message,
                ),
                exception=exc,
            )

        status = TOOL_SUCCESS

        return ToolResult(
            tool_name=invocation.tool_name,
            status=status,
            output=output,
            trace=_build_trace(
                invocation_id=invocation_id,
                invocation=invocation,
                definition=definition,
                status=status,
                started_at=started_at,
            ),
        )


def _build_trace(
    *,
    invocation_id: str,
    invocation: ToolInvocation,
    definition: ToolDefinition | None,
    status: str,
    started_at: float,
    error_type: str | None = None,
    error_message: str | None = None,
) -> ToolExecutionTrace:
    duration_ms = max(
        0.0,
        (
            perf_counter()
            - started_at
        )
        * 1000.0,
    )

    return ToolExecutionTrace(
        invocation_id=invocation_id,
        tool_name=invocation.tool_name,
        tool_source=(
            definition.source
            if definition is not None
            else "unknown"
        ),
        status=status,
        duration_ms=duration_ms,
        error_type=error_type,
        error_message=error_message,
        arguments=dict(
            invocation.arguments
        ),
        metadata={
            "read_only": (
                definition.read_only
                if definition is not None
                else None
            )
        },
    )


def _validate_arguments(
    definition: ToolDefinition,
    arguments: dict[str, Any],
) -> str | None:
    # MCP and other protocol-native tools may expose full JSON Schema
    # constructs that cannot be represented losslessly by ToolParameter.
    # The flat view is used only for deterministic basic validation;
    # protocol/server-side validation remains authoritative.
    declared = {
        parameter.name:
            parameter
        for parameter
        in definition.parameters
    }

    missing = [
        parameter.name
        for parameter
        in definition.parameters
        if (
            parameter.required
            and parameter.name
            not in arguments
        )
    ]

    if missing:
        return (
            "Missing required arguments: "
            + ", ".join(
                sorted(missing)
            )
        )

    unknown = sorted(
        set(arguments)
        - set(declared)
    )

    if unknown:
        return (
            "Unknown arguments: "
            + ", ".join(
                unknown
            )
        )

    return None


def serialize_tool_trace_for_persistence(
    trace: ToolExecutionTrace | None,
) -> dict[str, Any] | None:
    """Return a replay-safe tool trace without raw invocation arguments.

    Runtime arguments may contain queries, internal identifiers, or future
    MCP payloads. Persisted observability therefore keeps operational
    metadata only.

    This data is observability only and must never become decision truth.
    """

    if trace is None:
        return None

    return {
        "invocation_id": trace.invocation_id,
        "tool_name": trace.tool_name,
        "tool_source": trace.tool_source,
        "status": trace.status,
        "duration_ms": trace.duration_ms,
        "error_type": trace.error_type,
        "error_message": trace.error_message,
        "metadata": dict(trace.metadata),
    }
