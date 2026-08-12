from models import ExecutionEvent, SummaryState


def test_summary_state_contains_execution_events() -> None:
    state = SummaryState(
        research_topic="test topic"
    )

    event = ExecutionEvent(
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    state.execution_events.append(event)

    assert len(state.execution_events) == 1
    assert state.execution_events[0].event_type == "task_started"


def test_summary_state_execution_events_defaults_empty() -> None:
    state = SummaryState(
        research_topic="test topic"
    )

    assert state.execution_events == []
