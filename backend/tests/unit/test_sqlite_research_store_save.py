import json
import sqlite3

from models import ExecutionEvent, ExecutionTrace, SummaryState, TodoItem
from services.research_store import SQLiteResearchStore


def test_sqlite_store_initializes_schema(tmp_path) -> None:
    db_path = tmp_path / "research.db"

    SQLiteResearchStore(db_path)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

    table_names = {row[0] for row in rows}

    assert {
        "research_runs",
        "todo_items",
        "execution_traces",
        "execution_events",
    }.issubset(table_names)


def test_sqlite_store_saves_complete_research_state(tmp_path) -> None:
    db_path = tmp_path / "research.db"

    store = SQLiteResearchStore(db_path)

    state = SummaryState(
        research_topic="SQLite persistence",
        search_query="sqlite test query",
        research_loop_count=2,
        running_summary="running summary",
        structured_report="# Final report",
        report_note_id="note_report",
        report_note_path="/tmp/report.md",
        todo_items=[
            TodoItem(
                id=1,
                title="Investigate persistence",
                intent="Understand SQLite persistence",
                query="sqlite persistence",
                status="completed",
                summary="Task completed",
                sources_summary="Source summary",
                notices=["notice-1"],
                note_id="note_1",
                note_path="/tmp/note_1.md",
                stream_token="stream_1",
            )
        ],
        execution_traces=[
            ExecutionTrace(
                trace_id="trace_test",
                task_id=1,
                status="completed",
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:00:01+00:00",
                duration_ms=1000.0,
                current_stage="completed",
                retry_count=1,
            )
        ],
        execution_event_history=[
            ExecutionEvent(
                event_id="evt_test",
                trace_id="trace_test",
                task_id=1,
                schema_version=1,
                timestamp="2026-01-01T00:00:00+00:00",
                event_type="task_started",
                stage="execution",
                metadata={"source": "unit-test"},
            )
        ],
    )

    research_id = store.save(state)

    assert research_id.startswith("research_")

    with sqlite3.connect(db_path) as connection:
        research_row = connection.execute(
            """
            SELECT research_topic, structured_report
            FROM research_runs
            WHERE research_id = ?
            """,
            (research_id,),
        ).fetchone()

        todo_row = connection.execute(
            """
            SELECT task_id, title, notices_json
            FROM todo_items
            WHERE research_id = ?
            """,
            (research_id,),
        ).fetchone()

        trace_row = connection.execute(
            """
            SELECT trace_id, task_id, status
            FROM execution_traces
            WHERE research_id = ?
            """,
            (research_id,),
        ).fetchone()

        event_row = connection.execute(
            """
            SELECT event_id, trace_id, metadata_json
            FROM execution_events
            WHERE research_id = ?
            """,
            (research_id,),
        ).fetchone()

    assert research_row == (
        "SQLite persistence",
        "# Final report",
    )

    assert todo_row[0] == 1
    assert todo_row[1] == "Investigate persistence"
    assert json.loads(todo_row[2]) == ["notice-1"]

    assert trace_row == (
        "trace_test",
        1,
        "completed",
    )

    assert event_row[0] == "evt_test"
    assert event_row[1] == "trace_test"
    assert json.loads(event_row[2]) == {
        "source": "unit-test",
    }


def test_sqlite_store_persists_event_history_not_stream_buffer(tmp_path) -> None:
    db_path = tmp_path / "research.db"

    store = SQLiteResearchStore(db_path)

    state = SummaryState(
        research_topic="Event persistence",
        execution_traces=[
            ExecutionTrace(
                trace_id="trace_history",
                task_id=1,
                status="completed",
            )
        ],
        execution_events=[
            ExecutionEvent(
                event_id="evt_buffer",
                trace_id="trace_buffer",
                task_id=1,
                event_type="temporary",
                stage="stream",
            )
        ],
        execution_event_history=[
            ExecutionEvent(
                event_id="evt_history",
                trace_id="trace_history",
                task_id=1,
                event_type="task_completed",
                stage="completed",
            )
        ],
    )

    research_id = store.save(state)

    with sqlite3.connect(db_path) as connection:
        event_ids = connection.execute(
            """
            SELECT event_id
            FROM execution_events
            WHERE research_id = ?
            """,
            (research_id,),
        ).fetchall()

    assert event_ids == [("evt_history",)]
