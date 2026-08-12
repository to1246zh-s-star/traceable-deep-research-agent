from fastapi.testclient import TestClient

import main as main_module
from models import (
    ExecutionEvent,
    ExecutionTrace,
    SummaryState,
    SummaryStateOutput,
    TodoItem,
)


class FakeDeepResearchAgent:
    """Deterministic agent used to test API persistence without external calls."""

    def __init__(self, config) -> None:
        self.config = config
        self._last_state = None

    @property
    def last_state(self):
        return self._last_state

    def run(self, topic: str) -> SummaryStateOutput:
        todo = TodoItem(
            id=1,
            title="Persistence task",
            intent="Verify durable API state",
            query="sqlite persistence",
            status="completed",
            summary="Persistence verified",
            sources_summary="Test source",
        )

        trace = ExecutionTrace(
            trace_id="trace_api_restart",
            task_id=1,
            status="completed",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            duration_ms=1000.0,
            current_stage="completed",
        )

        event = ExecutionEvent(
            event_id="evt_api_restart",
            trace_id=trace.trace_id,
            task_id=1,
            timestamp="2026-01-01T00:00:01+00:00",
            event_type="task_completed",
            stage="completed",
            metadata={"source": "api-restart-test"},
        )

        self._last_state = SummaryState(
            research_topic=topic,
            todo_items=[todo],
            execution_traces=[trace],
            execution_event_history=[event],
            structured_report="# Persistent report",
        )

        return SummaryStateOutput(
            running_summary="Persistent report",
            report_markdown="# Persistent report",
            todo_items=[todo],
        )


def test_research_trace_survives_new_app_instance(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "research.db"

    monkeypatch.setenv(
        "RESEARCH_DB_PATH",
        str(db_path),
    )

    monkeypatch.setattr(
        main_module,
        "DeepResearchAgent",
        FakeDeepResearchAgent,
    )

    app_a = main_module.create_app()

    with TestClient(app_a) as client_a:
        response = client_a.post(
            "/research",
            json={"topic": "Durable observability"},
        )

        assert response.status_code == 200

        payload = response.json()

        research_id = payload["research_id"]

        assert research_id.startswith("research_")
        assert payload["report_markdown"] == "# Persistent report"

    assert db_path.exists()

    # Simulate a server restart by constructing a completely new app,
    # which creates a new SQLiteResearchStore instance using the same DB.
    app_b = main_module.create_app()

    with TestClient(app_b) as client_b:
        traces_response = client_b.get(
            f"/research/{research_id}/traces"
        )

        assert traces_response.status_code == 200

        traces_payload = traces_response.json()

        assert traces_payload["research_id"] == research_id
        assert len(traces_payload["traces"]) == 1
        assert (
            traces_payload["traces"][0]["trace_id"]
            == "trace_api_restart"
        )

        detail_response = client_b.get(
            f"/research/{research_id}/traces/trace_api_restart"
        )

        assert detail_response.status_code == 200

        detail = detail_response.json()

        assert detail["trace"]["task_id"] == 1
        assert detail["trace"]["status"] == "completed"

        assert len(detail["events"]) == 1
        assert detail["events"][0]["event_id"] == "evt_api_restart"
        assert (
            detail["events"][0]["trace_id"]
            == "trace_api_restart"
        )


def test_configuration_reads_research_db_path(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "configured.db"

    monkeypatch.setenv(
        "RESEARCH_DB_PATH",
        str(db_path),
    )

    config = main_module.Configuration.from_env()

    assert config.research_db_path == str(db_path)
