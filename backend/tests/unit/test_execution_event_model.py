from models import ExecutionEvent


def test_execution_event_requires_basic_fields() -> None:
    event = ExecutionEvent(
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    assert event.task_id == 1
    assert event.event_type == "task_started"
    assert event.stage == "executor"


def test_execution_event_has_timestamp() -> None:
    event = ExecutionEvent(
        task_id=1,
        event_type="search_started",
        stage="search",
    )

    assert event.timestamp is not None


def test_execution_event_metadata_defaults_to_empty_dict() -> None:
    event = ExecutionEvent(
        task_id=1,
        event_type="search_finished",
        stage="search",
    )

    assert event.metadata == {}


def test_execution_event_keeps_metadata() -> None:
    event = ExecutionEvent(
        task_id=1,
        event_type="task_completed",
        stage="executor",
        metadata={
            "duration_ms": 1200,
            "sources": 3,
        },
    )

    assert event.metadata["duration_ms"] == 1200
    assert event.metadata["sources"] == 3
