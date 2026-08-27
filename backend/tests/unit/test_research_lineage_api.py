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


def test_get_lineage_returns_initial_run_metadata():
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
        f"/research/{research_id}/lineage"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == research_id

    assert (
        payload["root_research_id"]
        == research_id
    )

    assert payload["parent_research_id"] is None
    assert payload["version_number"] == 1

    assert (
        payload["creation_reason"]
        == "initial_research"
    )


def test_get_lineage_returns_404_for_unknown_run():
    app = make_app()
    client = TestClient(app)

    response = client.get(
        "/research/research_missing/lineage"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Research run not found"
    )


def test_get_versions_returns_full_ordered_chain():
    app = make_app()
    client = TestClient(app)

    v1 = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v1",
            )
        )
    )

    v2 = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v2",
            ),
            parent_research_id=v1,
            creation_reason="reevaluation",
            created_from_trigger_ids=[
                "trg_a",
            ],
        )
    )

    v3 = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v3",
            ),
            parent_research_id=v2,
            creation_reason="reevaluation",
            created_from_trigger_ids=[
                "trg_b",
            ],
        )
    )

    response = client.get(
        f"/research/{v3}/versions"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == v3
    assert payload["root_research_id"] == v1

    versions = payload["versions"]

    assert [
        item["research_id"]
        for item in versions
    ] == [
        v1,
        v2,
        v3,
    ]

    assert [
        item["version_number"]
        for item in versions
    ] == [
        1,
        2,
        3,
    ]

    assert (
        versions[1][
            "created_from_trigger_ids"
        ]
        == ["trg_a"]
    )

    assert (
        versions[2][
            "created_from_trigger_ids"
        ]
        == ["trg_b"]
    )


def test_get_versions_from_middle_version_returns_whole_chain():
    app = make_app()
    client = TestClient(app)

    v1 = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v1",
            )
        )
    )

    v2 = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v2",
            ),
            parent_research_id=v1,
            creation_reason="reevaluation",
        )
    )

    v3 = (
        app.state.research_store.save(
            SummaryState(
                research_topic="v3",
            ),
            parent_research_id=v2,
            creation_reason="reevaluation",
        )
    )

    response = client.get(
        f"/research/{v2}/versions"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["root_research_id"] == v1

    assert [
        item["research_id"]
        for item in payload["versions"]
    ] == [
        v1,
        v2,
        v3,
    ]


def test_get_versions_returns_404_for_unknown_run():
    app = make_app()
    client = TestClient(app)

    response = client.get(
        "/research/research_missing/versions"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Research run not found"
    )


def test_lineage_api_does_not_expose_decision_state():
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
        f"/research/{research_id}/lineage"
    ).json()

    assert "decision" not in payload
    assert "decision_case" not in payload
    assert "readiness" not in payload
    assert "recommendation" not in payload
    assert "research_analysis" not in payload
