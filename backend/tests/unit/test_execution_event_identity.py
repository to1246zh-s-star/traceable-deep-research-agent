from models import ExecutionEvent


def test_execution_event_has_unique_id():
    event1 = ExecutionEvent(
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    event2 = ExecutionEvent(
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    assert event1.event_id.startswith("evt_")
    assert event2.event_id.startswith("evt_")
    assert event1.event_id != event2.event_id


def test_execution_event_has_timestamp():
    event = ExecutionEvent(
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    assert event.timestamp is not None
