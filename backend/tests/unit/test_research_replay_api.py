from fastapi.testclient import TestClient

from main import create_app
from models import (
    Claim,
    Evidence,
    ExecutionEvent,
    ExecutionTrace,
    SummaryState,
    TodoItem,
)


def make_state() -> SummaryState:
    state = SummaryState(
        research_topic="Qdrant vs Milvus",
    )

    state.todo_items = [
        TodoItem(
            id=1,
            title="Compare reliability",
            intent="Compare operational reliability",
            query="Qdrant Milvus reliability",
            status="completed",
        )
    ]

    state.execution_traces = [
        ExecutionTrace(
            trace_id="trace_test",
            task_id=1,
            status="completed",
            started_at="2026-08-13T01:00:00+00:00",
            finished_at="2026-08-13T01:01:00+00:00",
        )
    ]

    state.execution_events = [
        ExecutionEvent(
            event_id="evt_test",
            trace_id="trace_test",
            task_id=1,
            event_type="search_completed",
            stage="search",
            timestamp="2026-08-13T01:00:30+00:00",
        )
    ]

    state.evidence_items = [
        Evidence(
            evidence_id="evi_test",
            task_id=1,
            trace_id="trace_test",
            query="Qdrant Milvus reliability",
            backend="web",
            source_title="Benchmark",
            source_url="https://example.com/benchmark",
            snippet="Benchmark result",
            content="Benchmark result",
            source_rank=1,
            created_at="2026-08-13T01:00:40+00:00",
        )
    ]

    state.claims = [
        Claim(
            claim_id="clm_test",
            task_id=1,
            trace_id="trace_test",
            text="Qdrant has simpler operations in this benchmark.",
            evidence_ids=["evi_test"],
            created_at="2026-08-13T01:00:50+00:00",
        )
    ]

    return state


class FakeResearchStore:
    def __init__(self, state):
        self.state = state

    def get(self, research_id):
        if research_id == "research_test":
            return self.state

        return None


def test_replay_endpoint_aggregates_research_artifacts():
    app = create_app()
    app.state.research_store = FakeResearchStore(
        make_state()
    )

    client = TestClient(app)

    response = client.get(
        "/research/research_test/replay"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == "research_test"
    assert payload["research_topic"] == "Qdrant vs Milvus"

    assert payload["task_count"] == 1
    assert payload["trace_count"] == 1
    assert payload["claim_count"] == 1
    assert payload["evidence_count"] == 1

    task = payload["tasks"][0]

    assert task["task_id"] == 1
    assert task["trace_ids"] == ["trace_test"]
    assert task["claim_ids"] == ["clm_test"]
    assert task["evidence_ids"] == ["evi_test"]


def test_replay_timeline_is_chronological():
    app = create_app()
    app.state.research_store = FakeResearchStore(
        make_state()
    )

    client = TestClient(app)

    payload = client.get(
        "/research/research_test/replay"
    ).json()

    timestamps = [
        item["timestamp"]
        for item in payload["timeline"]
        if item["timestamp"] is not None
    ]

    assert timestamps == sorted(timestamps)

    event_types = {
        item["event_type"]
        for item in payload["timeline"]
    }

    assert "trace_started" in event_types
    assert "search_completed" in event_types
    assert "evidence_captured" in event_types
    assert "claim_grounded" in event_types
    assert "trace_completed" in event_types


def test_replay_endpoint_returns_404_for_unknown_run():
    app = create_app()
    app.state.research_store = FakeResearchStore(
        make_state()
    )

    client = TestClient(app)

    response = client.get(
        "/research/does-not-exist/replay"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Research run not found"
