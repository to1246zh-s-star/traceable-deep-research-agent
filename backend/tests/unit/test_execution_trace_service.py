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


def test_service_filters_execution_events():

    service = ExecutionTraceService(
        lock=Lock()
    )

    state = SummaryState(
        research_topic="test"
    )

    state.execution_event_history.extend(
        [
            ExecutionEvent(
                trace_id="trace_1",
                task_id=1,
                event_type="task_started",
                stage="executor",
            ),
            ExecutionEvent(
                trace_id="trace_1",
                task_id=1,
                event_type="task_completed",
                stage="executor",
            ),
            ExecutionEvent(
                trace_id="trace_2",
                task_id=2,
                event_type="task_failed",
                stage="search",
            ),
        ]
    )

    result = service.get_events(
        state,
        task_id=1,
        event_type="task_completed",
    )

    assert len(result) == 1
    assert result[0].task_id == 1
    assert result[0].event_type == "task_completed"


def test_service_summarizes_execution_events():

    service = ExecutionTraceService(
        lock=Lock()
    )

    state = SummaryState(
        research_topic="test"
    )

    state.execution_event_history.extend(
        [
            ExecutionEvent(
                trace_id="trace_1",
                task_id=1,
                event_type="task_started",
                stage="executor",
            ),
            ExecutionEvent(
                trace_id="trace_1",
                task_id=1,
                event_type="task_completed",
                stage="executor",
            ),
            ExecutionEvent(
                trace_id="trace_2",
                task_id=2,
                event_type="task_failed",
                stage="search",
            ),
            ExecutionEvent(
                trace_id="trace_3",
                task_id=3,
                event_type="task_skipped",
                stage="search",
            ),
        ]
    )

    result = service.summarize_events(state)

    assert result["total_events"] == 4
    assert result["completed_tasks"] == 1
    assert result["failed_tasks"] == 1
    assert result["skipped_tasks"] == 1
    assert result["event_counts"]["task_started"] == 1
    assert result["event_counts"]["task_completed"] == 1
    assert result["event_counts"]["task_failed"] == 1
    assert result["event_counts"]["task_skipped"] == 1
