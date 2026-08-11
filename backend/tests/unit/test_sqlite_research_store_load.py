from models import ExecutionEvent, ExecutionTrace, SummaryState, TodoItem
from services.research_store import SQLiteResearchStore


def test_sqlite_store_recovers_state_across_store_instances(tmp_path) -> None:
    db_path = tmp_path / "research.db"

    writer = SQLiteResearchStore(db_path)

    original = SummaryState(
        research_topic="Restart recovery",
        search_query="durable observability",
        research_loop_count=3,
        running_summary="running",
        structured_report="# Report",
        report_note_id="report_note",
        report_note_path="/tmp/report.md",
        todo_items=[
            TodoItem(
                id=1,
                title="Persist state",
                intent="Verify recovery",
                query="sqlite restart",
                status="completed",
                summary="done",
                sources_summary="sources",
                notices=["notice-a"],
                note_id="note_1",
                note_path="/tmp/note.md",
                stream_token="stream_1",
            )
        ],
        execution_traces=[
            ExecutionTrace(
                trace_id="trace_restart",
                task_id=1,
                status="completed",
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:00:01+00:00",
                duration_ms=1000.0,
                current_stage="completed",
                retry_count=2,
                error_type=None,
                error_message=None,
            )
        ],
        execution_event_history=[
            ExecutionEvent(
                event_id="evt_restart",
                trace_id="trace_restart",
                task_id=1,
                schema_version=1,
                timestamp="2026-01-01T00:00:00+00:00",
                event_type="task_completed",
                stage="completed",
                metadata={"source": "restart-test"},
            )
        ],
    )

    research_id = writer.save(original)

    reader = SQLiteResearchStore(db_path)
    restored = reader.get(research_id)

    assert restored is not None

    assert restored.research_topic == original.research_topic
    assert restored.search_query == original.search_query
    assert restored.research_loop_count == original.research_loop_count
    assert restored.running_summary == original.running_summary
    assert restored.structured_report == original.structured_report
    assert restored.report_note_id == original.report_note_id
    assert restored.report_note_path == original.report_note_path

    assert len(restored.todo_items) == 1
    restored_todo = restored.todo_items[0]
    assert restored_todo.id == 1
    assert restored_todo.title == "Persist state"
    assert restored_todo.notices == ["notice-a"]
    assert restored_todo.stream_token == "stream_1"

    assert len(restored.execution_traces) == 1
    restored_trace = restored.execution_traces[0]
    assert restored_trace.trace_id == "trace_restart"
    assert restored_trace.task_id == 1
    assert restored_trace.status == "completed"
    assert restored_trace.retry_count == 2

    assert restored.execution_events == []

    assert len(restored.execution_event_history) == 1
    restored_event = restored.execution_event_history[0]
    assert restored_event.event_id == "evt_restart"
    assert restored_event.trace_id == "trace_restart"
    assert restored_event.task_id == 1
    assert restored_event.metadata == {"source": "restart-test"}


def test_sqlite_store_get_returns_none_for_unknown_id(tmp_path) -> None:
    store = SQLiteResearchStore(tmp_path / "research.db")

    assert store.get("research_missing") is None


def test_sqlite_store_lists_recovered_states(tmp_path) -> None:
    store = SQLiteResearchStore(tmp_path / "research.db")

    first_id = store.save(
        SummaryState(research_topic="first")
    )
    second_id = store.save(
        SummaryState(research_topic="second")
    )

    recovered = SQLiteResearchStore(tmp_path / "research.db")
    items = recovered.list()

    assert [research_id for research_id, _ in items] == [
        first_id,
        second_id,
    ]

    assert [state.research_topic for _, state in items] == [
        "first",
        "second",
    ]
