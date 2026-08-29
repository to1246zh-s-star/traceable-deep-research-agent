from models import (
    RuntimeEfficiency,
    SummaryState,
)
from services.runtime_efficiency import (
    ensure_runtime_efficiency,
    finish_run_timer,
    record_llm_call,
)


def test_summary_state_has_runtime_efficiency():
    state = SummaryState()

    assert isinstance(
        state.runtime_efficiency,
        RuntimeEfficiency,
    )

    assert state.runtime_efficiency.latency_ms is None


def test_finish_run_timer_records_latency():
    state = SummaryState()

    finish_run_timer(
        state,
        started_counter=0.0,
    )

    assert state.runtime_efficiency.latency_ms is not None
    assert state.runtime_efficiency.latency_ms >= 0.0


def test_finish_run_timer_is_idempotent():
    state = SummaryState()

    finish_run_timer(
        state,
        started_counter=0.0,
    )

    first = state.runtime_efficiency.latency_ms

    finish_run_timer(
        state,
        started_counter=0.0,
    )

    assert state.runtime_efficiency.latency_ms == first


def test_finish_run_timer_can_overwrite():
    state = SummaryState()

    state.runtime_efficiency.latency_ms = 1.0

    finish_run_timer(
        state,
        started_counter=0.0,
        overwrite=True,
    )

    assert state.runtime_efficiency.latency_ms != 1.0


def test_missing_efficiency_is_recovered():
    state = SummaryState()
    state.runtime_efficiency = None

    result = ensure_runtime_efficiency(
        state
    )

    assert isinstance(
        result,
        RuntimeEfficiency,
    )


def test_llm_call_counter_is_explicit():
    state = SummaryState()

    record_llm_call(state)
    record_llm_call(state)

    assert state.runtime_efficiency.llm_call_count == 2


def test_token_and_cost_defaults_are_unknown():
    state = SummaryState()

    efficiency = state.runtime_efficiency

    assert efficiency.prompt_tokens is None
    assert efficiency.completion_tokens is None
    assert efficiency.total_tokens is None
    assert efficiency.estimated_cost is None
