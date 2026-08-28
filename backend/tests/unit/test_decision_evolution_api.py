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


def save_child(
    store,
    *,
    parent: str,
    topic: str,
):
    return store.save(
        SummaryState(
            research_topic=topic,
        ),
        parent_research_id=parent,
        creation_reason="reevaluation",
    )


def test_evolution_endpoint_resolves_root_from_child():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = save_child(
        store,
        parent=v1,
        topic="v2",
    )

    response = client.get(
        f"/research/{v2}/evolution"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["requested_research_id"]
        == v2
    )

    assert (
        payload["root_research_id"]
        == v1
    )


def test_evolution_endpoint_returns_linear_edges():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = save_child(
        store,
        parent=v1,
        topic="v2",
    )

    v3 = save_child(
        store,
        parent=v2,
        topic="v3",
    )

    payload = client.get(
        f"/research/{v3}/evolution"
    ).json()

    edges = [
        (
            step["source_research_id"],
            step["target_research_id"],
        )
        for step in payload["steps"]
    ]

    assert edges == [
        (v1, v2),
        (v2, v3),
    ]

    assert (
        payload["has_branches"]
        is False
    )

    assert (
        payload["leaf_version_ids"]
        == [v3]
    )


def test_evolution_endpoint_preserves_branches():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2_a = save_child(
        store,
        parent=v1,
        topic="v2 a",
    )

    v2_b = save_child(
        store,
        parent=v1,
        topic="v2 b",
    )

    payload = client.get(
        f"/research/{v1}/evolution"
    ).json()

    edges = {
        (
            step["source_research_id"],
            step["target_research_id"],
        )
        for step in payload["steps"]
    }

    assert edges == {
        (v1, v2_a),
        (v1, v2_b),
    }

    assert (
        payload["has_branches"]
        is True
    )

    assert (
        payload["branch_point_ids"]
        == [v1]
    )

    assert set(
        payload["leaf_version_ids"]
    ) == {
        v2_a,
        v2_b,
    }


def test_evolution_step_contains_phase41_diff():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    before = SummaryState(
        research_topic="v1",
    )

    after = SummaryState(
        research_topic="v2",
    )

    before.evidence_items = []

    after.evidence_items = [
        type(
            "EvidenceLike",
            (),
            {
                "evidence_id": "ev_new",
                "content": "new",
            },
        )()
    ]

    v1 = store.save(
        before
    )

    v2 = store.save(
        after,
        parent_research_id=v1,
        creation_reason="reevaluation",
    )

    payload = client.get(
        f"/research/{v2}/evolution"
    ).json()

    step = payload["steps"][0]

    assert (
        step["diff"]["source_research_id"]
        == v1
    )

    assert (
        step["diff"]["target_research_id"]
        == v2
    )

    assert (
        step["diff"]["summary_lines"]
        == [
            "Evidence: 1 added"
        ]
    )


def test_evolution_step_preserves_trigger_provenance():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = store.save(
        SummaryState(
            research_topic="v2",
        ),
        parent_research_id=v1,
        creation_reason="reevaluation",
        created_from_trigger_ids=[
            "trigger_security",
        ],
    )

    payload = client.get(
        f"/research/{v2}/evolution"
    ).json()

    step = payload["steps"][0]

    assert (
        step["target_creation_reason"]
        == "reevaluation"
    )

    assert (
        step["created_from_trigger_ids"]
        == ["trigger_security"]
    )


def test_evolution_endpoint_404_for_unknown_run():
    app = make_app()
    client = TestClient(app)

    response = client.get(
        "/research/research_missing/evolution"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Research run not found"
    )


def test_evolution_endpoint_requires_lineage_capability():
    class LegacyStore:
        def get(
            self,
            research_id,
        ):
            if research_id == "legacy":
                return SummaryState(
                    research_topic="legacy",
                )

            return None

    app = main.create_app()

    app.state.research_store = (
        LegacyStore()
    )

    client = TestClient(app)

    response = client.get(
        "/research/legacy/evolution"
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == (
            "Research lineage is unavailable "
            "for this store"
        )
    )


def test_evolution_response_has_no_quality_judgment():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = save_child(
        store,
        parent=v1,
        topic="v2",
    )

    payload = client.get(
        f"/research/{v2}/evolution"
    ).json()

    forbidden = {
        "better_version",
        "preferred_branch",
        "best_version",
        "quality_improved",
        "winner",
    }

    assert not (
        forbidden
        & set(payload)
    )

    assert not (
        forbidden
        & set(payload["steps"][0])
    )


def test_evolution_nested_diff_does_not_require_same_lineage_wrapper():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = save_child(
        store,
        parent=v1,
        topic="v2",
    )

    response = client.get(
        f"/research/{v2}/evolution"
    )

    assert response.status_code == 200

    payload = response.json()

    nested_diff = (
        payload["steps"][0]["diff"]
    )

    assert (
        nested_diff["source_research_id"]
        == v1
    )

    assert (
        nested_diff["target_research_id"]
        == v2
    )

    # same_lineage belongs to the standalone
    # cross-run diff API wrapper, not the
    # deterministic diff core.
    assert (
        "same_lineage"
        not in nested_diff
    )


def test_evolution_api_exposes_attribution_groups():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    before = SummaryState(
        research_topic="v1",
    )

    after = SummaryState(
        research_topic="v2",
    )

    before.evidence_items = []

    after.evidence_items = [
        type(
            "EvidenceLike",
            (),
            {
                "evidence_id": "ev_new",
                "content": "new",
            },
        )()
    ]

    v1 = store.save(
        before
    )

    v2 = store.save(
        after,
        parent_research_id=v1,
        creation_reason="reevaluation",
    )

    response = client.get(
        f"/research/{v2}/evolution"
    )

    assert response.status_code == 200

    payload = response.json()

    attribution = (
        payload["steps"][0][
            "attribution"
        ]
    )

    assert (
        attribution[
            "source_research_id"
        ]
        == v1
    )

    assert (
        attribution[
            "target_research_id"
        ]
        == v2
    )

    evidence_group = next(
        group
        for group
        in attribution["groups"]
        if group["section"]
        == "evidence"
    )

    assert (
        evidence_group["added_count"]
        == 1
    )

    assert (
        evidence_group["items"][0][
            "field_name"
        ]
        == "evidence.ev_new"
    )


def test_evolution_api_attribution_matches_nested_diff_identity():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = save_child(
        store,
        parent=v1,
        topic="v2",
    )

    payload = client.get(
        f"/research/{v2}/evolution"
    ).json()

    step = payload["steps"][0]

    assert (
        step["attribution"][
            "source_research_id"
        ]
        == step["diff"][
            "source_research_id"
        ]
    )

    assert (
        step["attribution"][
            "target_research_id"
        ]
        == step["diff"][
            "target_research_id"
        ]
    )

    assert (
        step["attribution"][
            "has_changes"
        ]
        == step["diff"][
            "has_changes"
        ]
    )


def test_evolution_api_attribution_exposes_no_causal_judgment():
    app = make_app()
    client = TestClient(app)
    store = app.state.research_store

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = save_child(
        store,
        parent=v1,
        topic="v2",
    )

    payload = client.get(
        f"/research/{v2}/evolution"
    ).json()

    attribution = (
        payload["steps"][0][
            "attribution"
        ]
    )

    forbidden = {
        "cause",
        "caused_by",
        "causal_effect",
        "driver",
        "preferred_version",
        "preferred_branch",
        "better_version",
        "quality_improved",
        "winner",
    }

    assert not (
        forbidden
        & set(attribution)
    )

    for group in attribution["groups"]:
        assert not (
            forbidden
            & set(group)
        )
