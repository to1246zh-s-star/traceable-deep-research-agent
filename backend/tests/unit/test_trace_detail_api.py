from fastapi.testclient import TestClient

import main
from models import ExecutionEvent, ExecutionTrace, SummaryState


def build_research_state() -> SummaryState:
    state = SummaryState(
        research_topic="test topic",
    )

    state.execution_traces.append(
        ExecutionTrace(
            trace_id="trace_1",
            task_id=1,
            status="completed",
            started_at="2026-08-11T10:00:00+00:00",
            finished_at="2026-08-11T10:00:01+00:00",
            duration_ms=1000.0,
        )
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
        ]
    )

    return state


def test_get_trace_with_related_events():
    app = main.create_app()
    client = TestClient(app)

    research_id = app.state.research_store.save(
        build_research_state()
    )

    response = client.get(
        f"/research/{research_id}/traces/trace_1"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == research_id
    assert payload["trace"]["trace_id"] == "trace_1"
    assert payload["trace"]["status"] == "completed"

    assert len(payload["events"]) == 2
    assert payload["events"][0]["trace_id"] == "trace_1"
    assert payload["events"][0]["event_type"] == "task_started"
    assert payload["events"][1]["event_type"] == "task_completed"


def test_get_trace_returns_404_for_unknown_research():
    app = main.create_app()
    client = TestClient(app)

    response = client.get(
        "/research/research_missing/traces/trace_1"
    )

    assert response.status_code == 404


def test_get_trace_returns_404_for_unknown_trace():
    app = main.create_app()
    client = TestClient(app)

    research_id = app.state.research_store.save(
        build_research_state()
    )

    response = client.get(
        f"/research/{research_id}/traces/trace_missing"
    )

    assert response.status_code == 404
