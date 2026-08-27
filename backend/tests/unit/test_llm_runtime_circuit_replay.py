from main import _build_research_replay
from models import SummaryState
from services.research_store import (
    _deserialize_v3_state,
    _serialize_v3_state,
)


def test_llm_runtime_circuit_round_trip():
    state = SummaryState(
        research_topic="test",
        llm_runtime_circuit={
            "status": "open",
            "error_type": "quota_exceeded",
            "trigger_stage": "task_summarization",
        },
    )

    raw = _serialize_v3_state(
        state
    )

    restored = _deserialize_v3_state(
        raw
    )

    assert restored[
        "llm_runtime_circuit"
    ] == state.llm_runtime_circuit


def test_replay_exposes_llm_runtime_circuit():
    state = SummaryState(
        research_topic="test",
        llm_runtime_circuit={
            "status": "open",
            "error_type": "quota_exceeded",
            "trigger_stage": "task_summarization",
        },
    )

    replay = _build_research_replay(
        "research_circuit",
        state,
    )

    assert replay[
        "llm_runtime_circuit"
    ] == {
        "status": "open",
        "error_type": "quota_exceeded",
        "trigger_stage": "task_summarization",
    }
