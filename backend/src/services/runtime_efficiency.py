"""Run-level Agent efficiency observability."""

from __future__ import annotations

from time import perf_counter

from models import (
    RuntimeEfficiency,
    SummaryState,
)
from services.llm_pricing import (
    LLMPricingRegistry,
    apply_trusted_cost_estimate,
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


def apply_llm_usage_snapshot(
    state: SummaryState,
    snapshot: dict[str, int | None],
) -> None:
    """Copy provider-observed LLM usage into run observability."""

    efficiency = ensure_runtime_efficiency(
        state
    )

    call_count = snapshot.get(
        "call_count"
    )

    if isinstance(
        call_count,
        int,
    ):
        efficiency.llm_call_count = max(
            0,
            call_count,
        )

    prompt_tokens = snapshot.get(
        "prompt_tokens"
    )

    completion_tokens = snapshot.get(
        "completion_tokens"
    )

    total_tokens = snapshot.get(
        "total_tokens"
    )

    efficiency.prompt_tokens = (
        prompt_tokens
        if isinstance(
            prompt_tokens,
            int,
        )
        else None
    )

    efficiency.completion_tokens = (
        completion_tokens
        if isinstance(
            completion_tokens,
            int,
        )
        else None
    )

    efficiency.total_tokens = (
        total_tokens
        if isinstance(
            total_tokens,
            int,
        )
        else None
    )

    calls_with_usage = snapshot.get(
        "calls_with_usage"
    )

    if (
        isinstance(call_count, int)
        and isinstance(
            calls_with_usage,
            int,
        )
    ):
        efficiency.llm_usage_complete = (
            call_count > 0
            and calls_with_usage
            == call_count
        )
    else:
        efficiency.llm_usage_complete = None

    if efficiency.llm_usage_complete is not True:
        # Partial token totals must not masquerade as full-run usage.
        efficiency.prompt_tokens = None
        efficiency.completion_tokens = None
        efficiency.total_tokens = None

    # Cost remains intentionally unknown until explicit trusted pricing
    # configuration exists.
    efficiency.estimated_cost = None
    efficiency.cost_currency = None
    efficiency.cost_basis = None


def finalize_llm_observability(
    state: SummaryState,
    snapshot: dict[str, int | None],
    *,
    provider: str | None,
    model_id: str | None,
    pricing_registry: LLMPricingRegistry,
) -> None:
    """Finalize provider usage first, then apply trusted explicit pricing."""

    apply_llm_usage_snapshot(state, snapshot)
    apply_trusted_cost_estimate(
        ensure_runtime_efficiency(state),
        provider=provider,
        model_id=model_id,
        registry=pricing_registry,
    )
