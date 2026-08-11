from fastapi.testclient import TestClient

import main
from models import ExecutionTrace, SummaryState


class FakeStreamingAgent:
    def __init__(self, config=None):
        self._last_state = None

    @property
    def last_state(self):
        return self._last_state

    def run_stream(self, topic: str):
        state = SummaryState(
            research_topic=topic,
        )

        state.execution_traces.append(
            ExecutionTrace(
                trace_id="trace_stream",
                task_id=1,
                status="completed",
            )
        )

        self._last_state = state

        yield {
            "type": "status",
            "message": "running",
        }

        yield {
            "type": "done",
        }


def test_stream_returns_research_id_after_completion(monkeypatch):
    monkeypatch.setattr(
        main,
        "DeepResearchAgent",
        FakeStreamingAgent,
    )

    app = main.create_app()
    client = TestClient(app)

    response = client.post(
        "/research/stream",
        json={
            "topic": "stream topic",
        },
    )

    assert response.status_code == 200

    body = response.text

    assert '"type": "research_stored"' in body
    assert '"research_id": "research_' in body


def test_stream_saved_state_can_be_queried(monkeypatch):
    monkeypatch.setattr(
        main,
        "DeepResearchAgent",
        FakeStreamingAgent,
    )

    app = main.create_app()
    client = TestClient(app)

    response = client.post(
        "/research/stream",
        json={
            "topic": "stream topic",
        },
    )

    lines = [
        line
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]

    import json

    events = [
        json.loads(line.removeprefix("data: "))
        for line in lines
    ]

    stored_event = next(
        event
        for event in events
        if event["type"] == "research_stored"
    )

    research_id = stored_event["research_id"]

    trace_response = client.get(
        f"/research/{research_id}/traces"
    )

    assert trace_response.status_code == 200

    payload = trace_response.json()

    assert len(payload["traces"]) == 1
    assert payload["traces"][0]["trace_id"] == "trace_stream"
