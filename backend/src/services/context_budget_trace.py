"""Sanitized persistence bridge for context-budget observability."""

from __future__ import annotations

from threading import Lock

from models import (
    ContextBudgetTrace,
    ContextBudgetTraceDecision,
    SummaryState,
)

from services.context_engineering import (
    ContextBudgetResult,
)


_TRACE_LOCK = Lock()


def build_context_budget_trace(
    result: ContextBudgetResult,
) -> ContextBudgetTrace:
    """
    Convert runtime budget decisions into a sanitized persistent trace.

    Section content, prompts, evidence bodies, and model outputs are
    intentionally excluded.
    """

    return ContextBudgetTrace(
        purpose=result.purpose,
        available_units=max(
            0,
            result.available_units,
        ),
        used_units=max(
            0,
            result.used_units,
        ),
        overflow=bool(
            result.overflow
        ),
        decisions=[
            ContextBudgetTraceDecision(
                section_name=
                    decision.section_name,
                estimated_units=max(
                    0,
                    decision.estimated_units,
                ),
                priority=
                    decision.priority,
                included=bool(
                    decision.included
                ),
                reason=
                    decision.reason,
            )
            for decision in result.decisions
        ],
    )


def record_context_budget_trace(
    state: SummaryState,
    result: ContextBudgetResult,
) -> ContextBudgetTrace:
    """Append one sanitized budget trace to runtime state."""

    trace = build_context_budget_trace(
        result
    )

    with _TRACE_LOCK:
        state.context_budget_traces.append(
            trace
        )

    return trace
