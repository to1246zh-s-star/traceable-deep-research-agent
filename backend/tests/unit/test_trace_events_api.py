from fastapi.testclient import TestClient

import main
from models import ExecutionEvent, ExecutionTrace, SummaryState


def build_state() -> SummaryState:
    state = SummaryState(
        research_topic="test topic",
    )

    state.execution_traces.extend(
        [
            ExecutionTrace(
                trace_id="trace_1",
                task_id=1,
                status="completed",
            ),
            ExecutionTrace(
                trace_id="trace_2",
                task_id=2,
                status="failed",
            ),
        ]
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

    return state


def test_get_trace_events():
    app = main.create_app()
    client = TestClient(app)

    research_id = app.state.research_store.save(
        build_state()
    )

    response = client.get(
        f"/research/{research_id}/traces/trace_1/events"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == research_id
    assert payload["trace_id"] == "trace_1"

    assert len(payload["events"]) == 2

    assert payload["events"][0]["trace_id"] == "trace_1"
    assert payload["events"][0]["event_type"] == "task_started"

    assert payload["events"][1]["trace_id"] == "trace_1"
    assert payload["events"][1]["event_type"] == "task_completed"


def test_get_trace_events_returns_404_for_unknown_research():
    app = main.create_app()
    client = TestClient(app)

    response = client.get(
        "/research/research_missing/traces/trace_1/events"
    )

    assert response.status_code == 404


def test_get_trace_events_returns_404_for_unknown_trace():
    app = main.create_app()
    client = TestClient(app)

    research_id = app.state.research_store.save(
        build_state()
    )

    response = client.get(
        f"/research/{research_id}/traces/trace_missing/events"
    )

    assert response.status_code == 404
