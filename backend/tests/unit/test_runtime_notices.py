from models import SummaryState
from services.runtime_notices import (
    MAX_NOTICE_MESSAGE_LENGTH,
    record_runtime_notice,
)


def test_records_structured_runtime_notice():
    state = SummaryState(
        research_topic="A vs B",
    )

    notice = record_runtime_notice(
        state,
        stage="integration_assessment",
        error=RuntimeError(
            "Error code: 429 - insufficient balance"
        ),
    )

    assert notice["stage"] == (
        "integration_assessment"
    )
    assert notice["error_type"] == (
        "quota_exceeded"
    )
    assert notice["degraded"] is True

    assert state.runtime_notices == [
        notice
    ]


def test_runtime_notice_accepts_metadata():
    state = SummaryState(
        research_topic="test",
    )

    notice = record_runtime_notice(
        state,
        stage="report_generation",
        error=RuntimeError(
            "429 rate limit"
        ),
        metadata={
            "fallback": "deterministic",
        },
    )

    assert notice["error_type"] == (
        "rate_limited"
    )

    assert notice["metadata"] == {
        "fallback": "deterministic",
    }


def test_runtime_notice_message_is_bounded():
    state = SummaryState(
        research_topic="test",
    )

    notice = record_runtime_notice(
        state,
        stage="provider",
        error=RuntimeError(
            "x" * 5000
        ),
    )

    assert len(notice["message"]) <= (
        MAX_NOTICE_MESSAGE_LENGTH + 3
    )
