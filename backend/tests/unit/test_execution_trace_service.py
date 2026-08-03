from threading import Lock

from models import (
    SummaryState,
    ExecutionTrace,
    ExecutionEvent,
)

from services.execution_trace import ExecutionTraceService


def test_service_serializes_trace():

    service = ExecutionTraceService(
        lock=Lock()
    )

    state = SummaryState(
        research_topic="test"
    )

    trace_id = "trace_test"

    state.execution_traces.append(
        ExecutionTrace(
            trace_id=trace_id,
            task_id=1,
            status="completed",
        )
    )

    state.execution_event_history.append(
        ExecutionEvent(
            trace_id=trace_id,
            task_id=1,
            event_type="task_completed",
            stage="executor",
        )
    )

    result = service.serialize_trace(
        state,
        trace_id,
    )

    assert result["trace"]["trace_id"] == trace_id
    assert result["events"][0]["event_type"] == "task_completed"
