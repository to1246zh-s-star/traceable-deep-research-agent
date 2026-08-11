from fastapi.testclient import TestClient

import main
from models import ExecutionTrace, SummaryState


def test_list_traces_for_research():
    app = main.create_app()
    client = TestClient(app)

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
                error_type="search_error",
                error_message="boom",
            ),
        ]
    )

    research_id = app.state.research_store.save(state)

    response = client.get(
        f"/research/{research_id}/traces"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == research_id
    assert len(payload["traces"]) == 2

    assert payload["traces"][0]["trace_id"] == "trace_1"
    assert payload["traces"][0]["status"] == "completed"

    assert payload["traces"][1]["trace_id"] == "trace_2"
    assert payload["traces"][1]["status"] == "failed"
    assert payload["traces"][1]["error_type"] == "search_error"


def test_list_traces_returns_404_for_unknown_research():
    app = main.create_app()
    client = TestClient(app)

    response = client.get(
        "/research/research_missing/traces"
    )

    assert response.status_code == 404
