"""Build deterministic Agent-evaluation observations from research state.

This module is an observation bridge only.

Important semantics:
- it never mutates SummaryState;
- it never recomputes decision truth;
- persisted tool traces are observability inputs only;
- unavailable measurements remain None / UNKNOWN downstream;
- latency, token usage and cost are not inferred from incomplete data.
"""

from __future__ import annotations

from typing import Any

from models import SummaryState
from services.agent_eval import EvalObservation


_TERMINAL_TASK_STATUSES = {
    "completed",
    "partial",
    "skipped",
}

_SUCCESSFUL_TOOL_STATUSES = {
    "SUCCESS",
}


def _normalized_status(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def _count_tasks_by_status(
    state: SummaryState,
    status: str,
) -> int:
    target = status.strip().lower()

    return sum(
        _normalized_status(
            getattr(task, "status", "")
        ).lower()
        == target
        for task in state.todo_items
    )


def _derive_run_completion(
    state: SummaryState,
) -> bool | None:
    """Infer only whether observed tasks reached non-failed terminal states."""

    tasks = list(
        state.todo_items
    )

    if not tasks:
        return None

    statuses = [
        _normalized_status(
            getattr(task, "status", "")
        ).lower()
        for task in tasks
    ]

    if any(
        status == "failed"
        for status in statuses
    ):
        return False

    if all(
        status in _TERMINAL_TASK_STATUSES
        for status in statuses
    ):
        return True

    return False


def _derive_final_answer_presence(
    state: SummaryState,
) -> bool:
    structured_report = getattr(
        state,
        "structured_report",
        None,
    )

    running_summary = getattr(
        state,
        "running_summary",
        None,
    )

    return bool(
        str(
            structured_report
            or running_summary
            or ""
        ).strip()
    )


def _tool_trace_dicts(
    state: SummaryState,
) -> list[dict[str, Any]]:
    raw = getattr(
        state,
        "tool_execution_traces",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):
        return []

    return [
        item
        for item in raw
        if isinstance(
            item,
            dict,
        )
    ]


def _tool_observation_counts(
    state: SummaryState,
) -> tuple[
    int,
    int,
    int,
    list[str],
]:
    traces = _tool_trace_dicts(
        state
    )

    successful = 0
    failed = 0
    names: list[str] = []

    for trace in traces:
        status = _normalized_status(
            trace.get("status")
        ).upper()

        name = _normalized_status(
            trace.get("tool_name")
        )

        if name:
            names.append(name)

        if (
            status
            in _SUCCESSFUL_TOOL_STATUSES
        ):
            successful += 1
        else:
            failed += 1

    return (
        len(traces),
        successful,
        failed,
        names,
    )


def _claim_grounding_counts(
    state: SummaryState,
) -> tuple[
    int,
    int,
    int,
]:
    claims = list(
        state.claims
    )

    grounded = 0
    unsupported = 0

    for claim in claims:
        evidence_ids = getattr(
            claim,
            "evidence_ids",
            None,
        )

        if evidence_ids:
            grounded += 1
        else:
            unsupported += 1

    return (
        len(claims),
        grounded,
        unsupported,
    )


def _adaptive_iteration_count(
    state: SummaryState,
) -> int | None:
    adaptive = getattr(
        state,
        "adaptive_research_state",
        None,
    )

    if adaptive is None:
        return None

    iteration_count = getattr(
        adaptive,
        "iteration_count",
        None,
    )

    if isinstance(
        iteration_count,
        int,
    ):
        return max(
            0,
            iteration_count,
        )

    iterations = getattr(
        adaptive,
        "iterations",
        None,
    )

    if isinstance(
        iterations,
        list,
    ):
        return len(
            iterations
        )

    return None


def build_eval_observation(
    state: SummaryState,
) -> EvalObservation:
    """Project one real research state into deterministic eval observations."""

    (
        tool_call_count,
        successful_tool_call_count,
        failed_tool_call_count,
        called_tool_names,
    ) = _tool_observation_counts(
        state
    )

    (
        claim_count,
        grounded_claim_count,
        unsupported_claim_count,
    ) = _claim_grounding_counts(
        state
    )

    return EvalObservation(
        completed=(
            _derive_run_completion(
                state
            )
        ),
        final_answer_present=(
            _derive_final_answer_presence(
                state
            )
        ),
        planned_task_count=len(
            state.todo_items
        ),
        completed_task_count=(
            _count_tasks_by_status(
                state,
                "completed",
            )
        ),
        failed_task_count=(
            _count_tasks_by_status(
                state,
                "failed",
            )
        ),
        tool_call_count=(
            tool_call_count
        ),
        successful_tool_call_count=(
            successful_tool_call_count
        ),
        failed_tool_call_count=(
            failed_tool_call_count
        ),
        called_tool_names=(
            called_tool_names
        ),
        evidence_count=len(
            state.evidence_items
        ),
        claim_count=claim_count,
        grounded_claim_count=(
            grounded_claim_count
        ),
        unsupported_claim_count=(
            unsupported_claim_count
        ),
        # Recovery cannot currently be reconstructed reliably from the
        # sanitized persisted trace alone. Keep it unknown rather than
        # inventing recovery semantics.
        recoverable_failure_count=None,
        recovered_failure_count=None,
        adaptive_iteration_count=(
            _adaptive_iteration_count(
                state
            )
        ),
        latency_ms=(
            getattr(
                getattr(
                    state,
                    "runtime_efficiency",
                    None,
                ),
                "latency_ms",
                None,
            )
        ),
        token_usage=(
            getattr(
                getattr(
                    state,
                    "runtime_efficiency",
                    None,
                ),
                "total_tokens",
                None,
            )
        ),
        estimated_cost=(
            getattr(
                getattr(
                    state,
                    "runtime_efficiency",
                    None,
                ),
                "estimated_cost",
                None,
            )
        ),
        metadata={
            "observation_source":
                "summary_state",
        },
    )
