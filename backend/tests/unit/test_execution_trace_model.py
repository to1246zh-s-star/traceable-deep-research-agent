from models import ExecutionTrace, SummaryState


def test_execution_trace_default_values() -> None:
    trace = ExecutionTrace(task_id=1)

    assert trace.task_id == 1
    assert trace.status == "pending"
    assert trace.started_at is None
    assert trace.finished_at is None
    assert trace.duration_ms is None
    assert trace.current_stage is None
    assert trace.retry_count == 0
    assert trace.error_type is None
    assert trace.error_message is None


def test_summary_state_stores_execution_traces() -> None:
    trace = ExecutionTrace(
        task_id=2,
        status="running",
        current_stage="search",
    )

    state = SummaryState(
        research_topic="Test topic",
        execution_traces=[trace],
    )

    assert len(state.execution_traces) == 1
    assert state.execution_traces[0].task_id == 2
    assert state.execution_traces[0].status == "running"
    assert state.execution_traces[0].current_stage == "search"


def test_summary_state_execution_traces_are_not_shared() -> None:
    first_state = SummaryState(research_topic="First")
    second_state = SummaryState(research_topic="Second")

    first_state.execution_traces.append(ExecutionTrace(task_id=1))

    assert len(first_state.execution_traces) == 1
    assert second_state.execution_traces == []
