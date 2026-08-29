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


def test_complete_llm_usage_is_persisted_to_efficiency():
    from services.runtime_efficiency import (
        apply_llm_usage_snapshot,
    )

    state = SummaryState()

    apply_llm_usage_snapshot(
        state,
        {
            "call_count": 2,
            "calls_with_usage": 2,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    )

    efficiency = state.runtime_efficiency

    assert efficiency.llm_call_count == 2
    assert efficiency.llm_usage_complete is True
    assert efficiency.prompt_tokens == 100
    assert efficiency.completion_tokens == 50
    assert efficiency.total_tokens == 150


def test_partial_llm_usage_stays_unknown():
    from services.runtime_efficiency import (
        apply_llm_usage_snapshot,
    )

    state = SummaryState()

    apply_llm_usage_snapshot(
        state,
        {
            "call_count": 2,
            "calls_with_usage": 1,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    )

    efficiency = state.runtime_efficiency

    assert efficiency.llm_call_count == 2
    assert efficiency.llm_usage_complete is False

    assert efficiency.prompt_tokens is None
    assert efficiency.completion_tokens is None
    assert efficiency.total_tokens is None


def test_cost_remains_unknown_after_usage_snapshot():
    from services.runtime_efficiency import (
        apply_llm_usage_snapshot,
    )

    state = SummaryState()

    apply_llm_usage_snapshot(
        state,
        {
            "call_count": 1,
            "calls_with_usage": 1,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    )

    assert state.runtime_efficiency.estimated_cost is None
    assert state.runtime_efficiency.cost_currency is None
    assert state.runtime_efficiency.cost_basis is None


def test_finalize_usage_then_applies_explicit_pricing():
    from decimal import Decimal

    from services.llm_pricing import LLMPricingRegistry, LLMPricingRule
    from services.runtime_efficiency import finalize_llm_observability

    state = SummaryState()
    registry = LLMPricingRegistry(
        [
            LLMPricingRule(
                provider="custom",
                model_id="priced-model",
                input_price_per_1m_tokens=Decimal("2"),
                output_price_per_1m_tokens=Decimal("4"),
                currency="USD",
            )
        ]
    )

    finalize_llm_observability(
        state,
        {
            "call_count": 1,
            "calls_with_usage": 1,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        },
        provider="custom",
        model_id="priced-model",
        pricing_registry=registry,
    )

    assert state.runtime_efficiency.llm_usage_complete is True
    assert state.runtime_efficiency.estimated_cost == 0.004
