from models import ExecutionEvent


def test_execution_event_has_schema_version():
    event = ExecutionEvent(
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    assert event.schema_version == 1
