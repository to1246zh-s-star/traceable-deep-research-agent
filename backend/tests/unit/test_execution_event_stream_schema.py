from models import ExecutionEvent


def test_stream_payload_contains_execution_event_schema_fields():
    event = ExecutionEvent(
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    payload = {
        "type": "execution_event",
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "task_id": event.task_id,
        "event_type": event.event_type,
        "stage": event.stage,
        "metadata": event.metadata,
    }

    assert payload["schema_version"] == 1
    assert payload["event_id"].startswith("evt_")
    assert payload["timestamp"] is not None
