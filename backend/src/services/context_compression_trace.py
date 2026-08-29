"""Sanitized persistence bridge for context-compression observability."""

from __future__ import annotations

from threading import Lock

from models import ContextCompressionTrace, SummaryState
from services.context_engineering import ContextCompressionResult


_TRACE_LOCK = Lock()


def build_context_compression_traces(
    result: ContextCompressionResult,
) -> list[ContextCompressionTrace]:
    """Return sanitized traces without prompts, content, or evidence bodies."""

    return [
        ContextCompressionTrace(
            section_name=decision.section_name,
            original_estimated_size=max(0, decision.original_estimated_units),
            compressed_estimated_size=max(0, decision.compressed_estimated_units),
            strategy=decision.strategy,
            reason=decision.reason,
        )
        for decision in result.decisions
    ]


def record_context_compression_traces(
    state: SummaryState,
    result: ContextCompressionResult,
) -> list[ContextCompressionTrace]:
    traces = build_context_compression_traces(result)
    with _TRACE_LOCK:
        state.context_compression_traces.extend(traces)
    return traces
