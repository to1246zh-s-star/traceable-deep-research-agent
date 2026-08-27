from main import _build_research_replay
from models import (
    Evidence,
    ExecutionTrace,
    SummaryState,
    TodoItem,
)


def test_replay_exposes_partial_task_failure_type():
    state = SummaryState(
        research_topic="A vs B",
    )

    task = TodoItem(
        id=1,
        title="Research A",
        intent="Collect evidence",
        query="A docs",
        status="partial",
        notices=[
            "summarization_failed:rate_limited",
        ],
    )

    state.todo_items = [task]

    state.execution_traces = [
        ExecutionTrace(
            trace_id="trace_partial",
            task_id=1,
            status="partial",
            error_type="rate_limited",
            error_message="429 rate limit",
        )
    ]

    state.evidence_items = [
        Evidence(
            evidence_id="evi_partial",
            task_id=1,
            trace_id="trace_partial",
            query="A docs",
            backend="tavily",
            source_title="Docs",
            source_url="https://example.com",
        )
    ]

    replay = _build_research_replay(
        "research_partial",
        state,
    )

    assert len(replay["tasks"]) == 1

    task_payload = replay["tasks"][0]

    assert task_payload["status"] == "partial"

    assert task_payload["notices"] == [
        "summarization_failed:rate_limited"
    ]

    assert task_payload["error_types"] == [
        "rate_limited"
    ]

    assert task_payload["evidence_ids"] == [
        "evi_partial"
    ]
