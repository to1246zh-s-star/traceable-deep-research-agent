from fastapi.testclient import TestClient

import main
from models import SummaryState
from services.research_store import (
    InMemoryResearchStore,
)


def make_app():
    app = main.create_app()
    app.state.research_store = (
        InMemoryResearchStore()
    )
    return app


def test_replay_exposes_initial_lineage():
    app = make_app()
    client = TestClient(app)

    research_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v1",
            )
        )
    )

    response = client.get(
        f"/research/{research_id}/replay"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["lineage"] is not None

    assert (
        payload["lineage"]["research_id"]
        == research_id
    )

    assert (
        payload["lineage"]["root_research_id"]
        == research_id
    )

    assert (
        payload["lineage"]["version_number"]
        == 1
    )

    assert len(payload["versions"]) == 1


def test_replay_exposes_complete_version_chain():
    app = make_app()
    client = TestClient(app)

    v1 = app.state.research_store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = app.state.research_store.save(
        SummaryState(
            research_topic="v2",
        ),
        parent_research_id=v1,
        creation_reason="reevaluation",
    )

    v3 = app.state.research_store.save(
        SummaryState(
            research_topic="v3",
        ),
        parent_research_id=v2,
        creation_reason="reevaluation",
    )

    response = client.get(
        f"/research/{v2}/replay"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["lineage"]["research_id"]
        == v2
    )

    assert (
        payload["lineage"]["root_research_id"]
        == v1
    )

    assert [
        item["research_id"]
        for item in payload["versions"]
    ] == [
        v1,
        v2,
        v3,
    ]


def test_replay_lineage_remains_outside_decision_payload():
    app = make_app()
    client = TestClient(app)

    research_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v1",
            )
        )
    )

    payload = client.get(
        f"/research/{research_id}/replay"
    ).json()

    decision = payload.get(
        "decision"
    )

    if decision is not None:
        assert "lineage" not in decision
        assert "versions" not in decision


def test_replay_gracefully_omits_lineage_for_legacy_store():
    class LegacyStore:
        def __init__(self):
            self.state = SummaryState(
                research_topic="legacy",
            )

        def get(
            self,
            research_id,
        ):
            if research_id == "research_legacy":
                return self.state

            return None

    app = main.create_app()
    app.state.research_store = LegacyStore()

    client = TestClient(app)

    response = client.get(
        "/research/research_legacy/replay"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["lineage"] is None
    assert payload["versions"] == []
