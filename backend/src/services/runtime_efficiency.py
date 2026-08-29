"""Run-level Agent efficiency observability."""

from __future__ import annotations

from time import perf_counter

from models import (
    RuntimeEfficiency,
    SummaryState,
)


def ensure_runtime_efficiency(
    state: SummaryState,
) -> RuntimeEfficiency:
    """Return a backward-compatible runtime efficiency state."""

    efficiency = getattr(
        state,
        "runtime_efficiency",
        None,
    )

    if not isinstance(
        efficiency,
        RuntimeEfficiency,
    ):
        efficiency = RuntimeEfficiency()
        state.runtime_efficiency = efficiency

    return efficiency


def start_run_timer() -> float:
    """Return a monotonic run-level timer token."""

    return perf_counter()


def finish_run_timer(
    state: SummaryState,
    *,
    started_counter: float,
    overwrite: bool = False,
) -> None:
    """Persist true run-level wall-clock latency."""

    efficiency = ensure_runtime_efficiency(
        state
    )

    if (
        efficiency.latency_ms is not None
        and not overwrite
    ):
        return

    efficiency.latency_ms = max(
        0.0,
        (
            perf_counter()
            - started_counter
        )
        * 1000.0,
    )


def record_llm_call(
    state: SummaryState,
) -> None:
    """Increment an explicitly observed LLM-call counter."""

    efficiency = ensure_runtime_efficiency(
        state
    )

    efficiency.llm_call_count = (
        max(
            0,
            efficiency.llm_call_count,
        )
        + 1
    )
