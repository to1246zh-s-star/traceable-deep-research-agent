from models import SummaryState
from services.llm_runtime_circuit import (
    get_llm_circuit,
    is_llm_circuit_open,
    is_terminal_llm_error,
    open_llm_circuit,
    record_circuit_skip,
)


def test_quota_error_is_terminal():
    error = RuntimeError(
        "Error code: 429 - insufficient balance"
    )

    assert is_terminal_llm_error(error)


def test_authentication_error_is_terminal():
    error = RuntimeError(
        "401 invalid api key"
    )

    assert is_terminal_llm_error(error)


def test_rate_limit_is_not_terminal():
    error = RuntimeError(
        "429 rate limit"
    )

    assert not is_terminal_llm_error(error)


def test_timeout_is_not_terminal():
    error = TimeoutError(
        "provider timed out"
    )

    assert not is_terminal_llm_error(error)


def test_terminal_error_opens_per_run_circuit():
    state = SummaryState(
        research_topic="test",
    )

    changed = open_llm_circuit(
        state,
        error=RuntimeError(
            "429 insufficient balance"
        ),
        trigger_stage="task_summarization",
    )

    assert changed is True
    assert is_llm_circuit_open(state)

    circuit = get_llm_circuit(state)

    assert circuit["status"] == "open"
    assert circuit["error_type"] == (
        "quota_exceeded"
    )
    assert circuit["trigger_stage"] == (
        "task_summarization"
    )


def test_transient_failure_does_not_open_circuit():
    state = SummaryState(
        research_topic="test",
    )

    changed = open_llm_circuit(
        state,
        error=RuntimeError(
            "429 rate limit"
        ),
        trigger_stage="semantic_signal_extraction",
    )

    assert changed is False
    assert not is_llm_circuit_open(state)


def test_open_is_idempotent():
    state = SummaryState(
        research_topic="test",
    )

    first = open_llm_circuit(
        state,
        error=RuntimeError(
            "429 insufficient balance"
        ),
        trigger_stage="first",
    )

    second = open_llm_circuit(
        state,
        error=RuntimeError(
            "401 invalid api key"
        ),
        trigger_stage="second",
    )

    assert first is True
    assert second is False

    circuit = get_llm_circuit(state)

    assert circuit["trigger_stage"] == "first"


def test_circuit_skip_notice_is_deduplicated():
    state = SummaryState(
        research_topic="test",
    )

    open_llm_circuit(
        state,
        error=RuntimeError(
            "429 insufficient balance"
        ),
        trigger_stage="semantic_signal_extraction",
    )

    record_circuit_skip(
        state,
        stage="integration_assessment",
    )
    record_circuit_skip(
        state,
        stage="integration_assessment",
    )

    skips = [
        notice
        for notice in state.runtime_notices
        if (
            notice["stage"]
            == "integration_assessment"
            and notice["error_type"]
            == "llm_circuit_open"
        )
    ]

    assert len(skips) == 1
