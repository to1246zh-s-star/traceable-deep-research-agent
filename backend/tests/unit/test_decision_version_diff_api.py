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


def test_diff_endpoint_compares_source_to_target():
    app = make_app()
    client = TestClient(app)

    source = SummaryState(
        research_topic="v1",
    )

    target = SummaryState(
        research_topic="v2",
    )

    source.evidence_items = []
    target.evidence_items = []

    source_id = (
        app.state.research_store.save(
            source
        )
    )

    target_id = (
        app.state.research_store.save(
            target,
            parent_research_id=source_id,
            creation_reason="reevaluation",
        )
    )

    response = client.get(
        f"/research/{target_id}/diff/{source_id}"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["source_research_id"]
        == source_id
    )

    assert (
        payload["target_research_id"]
        == target_id
    )

    assert payload["same_lineage"] is True


def test_diff_endpoint_reports_persisted_evidence_change():
    app = make_app()
    client = TestClient(app)

    source = SummaryState(
        research_topic="v1",
    )

    target = SummaryState(
        research_topic="v2",
    )

    source.evidence_items = []

    target.evidence_items = [
        type(
            "EvidenceLike",
            (),
            {
                "evidence_id": "ev_new",
                "content": "new evidence",
            },
        )()
    ]

    source_id = (
        app.state.research_store.save(
            source
        )
    )

    target_id = (
        app.state.research_store.save(
            target,
            parent_research_id=source_id,
            creation_reason="reevaluation",
        )
    )

    response = client.get(
        f"/research/{target_id}/diff/{source_id}"
    )

    assert response.status_code == 200

    payload = response.json()

    changes = payload[
        "evidence_changes"
    ]

    assert len(changes) == 1

    assert (
        changes[0]["field_name"]
        == "evidence.ev_new"
    )

    assert (
        changes[0]["change_type"]
        == "ADDED"
    )


def test_diff_endpoint_cross_root_marks_not_same_lineage():
    app = make_app()
    client = TestClient(app)

    source_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="A",
            )
        )
    )

    target_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="B",
            )
        )
    )

    response = client.get(
        f"/research/{target_id}/diff/{source_id}"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["same_lineage"]
        is False
    )


def test_diff_endpoint_404_for_missing_source():
    app = make_app()
    client = TestClient(app)

    target_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="target",
            )
        )
    )

    response = client.get(
        f"/research/{target_id}/diff/research_missing"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Source research run not found"
    )


def test_diff_endpoint_404_for_missing_target():
    app = make_app()
    client = TestClient(app)

    source_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="source",
            )
        )
    )

    response = client.get(
        f"/research/research_missing/diff/{source_id}"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Target research run not found"
    )


def test_diff_endpoint_does_not_require_lineage_capability():
    class LegacyStore:
        def __init__(self):
            self.states = {
                "research_a": SummaryState(
                    research_topic="A",
                ),
                "research_b": SummaryState(
                    research_topic="B",
                ),
            }

        def get(
            self,
            research_id,
        ):
            return self.states.get(
                research_id
            )

    app = main.create_app()

    app.state.research_store = (
        LegacyStore()
    )

    client = TestClient(app)

    response = client.get(
        "/research/research_b/diff/research_a"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["same_lineage"]
        is False
    )


def test_diff_api_exposes_no_quality_judgment():
    app = make_app()
    client = TestClient(app)

    source_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v1",
            )
        )
    )

    target_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v2",
            ),
            parent_research_id=source_id,
            creation_reason="reevaluation",
        )
    )

    payload = client.get(
        f"/research/{target_id}/diff/{source_id}"
    ).json()

    forbidden = {
        "better",
        "improved",
        "improvement",
        "quality_change",
        "winner",
        "preferred_version",
    }

    assert not (
        forbidden
        & set(payload)
    )


def test_diff_api_exposes_deterministic_summary_lines():
    app = make_app()
    client = TestClient(app)

    source = SummaryState(
        research_topic="v1",
    )

    target = SummaryState(
        research_topic="v2",
    )

    source.evidence_items = []

    target.evidence_items = [
        type(
            "EvidenceLike",
            (),
            {
                "evidence_id": "ev_1",
                "content": "new",
            },
        )()
    ]

    source_id = (
        app.state.research_store.save(
            source
        )
    )

    target_id = (
        app.state.research_store.save(
            target,
            parent_research_id=source_id,
            creation_reason="reevaluation",
        )
    )

    payload = client.get(
        f"/research/{target_id}/diff/{source_id}"
    ).json()

    assert payload["summary_lines"] == [
        "Evidence: 1 added"
    ]


def test_standalone_diff_keeps_same_lineage_provenance():
    app = make_app()
    client = TestClient(app)

    source_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v1",
            )
        )
    )

    target_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v2",
            ),
            parent_research_id=source_id,
            creation_reason="reevaluation",
        )
    )

    response = client.get(
        f"/research/{target_id}/diff/{source_id}"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["same_lineage"]
        is True
    )
