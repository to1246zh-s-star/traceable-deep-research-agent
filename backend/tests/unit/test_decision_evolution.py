from models import (
    ResearchLineage,
    SummaryState,
)
from services.decision_evolution import (
    build_decision_evolution,
)


def state(
    topic: str,
) -> SummaryState:
    return SummaryState(
        research_topic=topic,
    )


def lineage(
    *,
    research_id: str,
    root: str,
    parent: str | None,
    version: int,
    reason: str = "reevaluation",
    triggers: list[str] | None = None,
) -> ResearchLineage:
    return ResearchLineage(
        research_id=research_id,
        root_research_id=root,
        parent_research_id=parent,
        version_number=version,
        creation_reason=reason,
        created_from_trigger_ids=(
            triggers or []
        ),
    )


def test_single_root_has_no_steps():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
            reason="initial_research",
        )
    ]

    states = {
        "v1": state("v1"),
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    assert timeline.steps == []
    assert timeline.has_branches is False
    assert timeline.root_version_ids == [
        "v1"
    ]
    assert timeline.leaf_version_ids == [
        "v1"
    ]


def test_linear_lineage_builds_parent_child_edges():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
            reason="initial_research",
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
        ),
        lineage(
            research_id="v3",
            root="v1",
            parent="v2",
            version=3,
        ),
    ]

    states = {
        "v1": state("v1"),
        "v2": state("v2"),
        "v3": state("v3"),
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    assert [
        (
            step.source_research_id,
            step.target_research_id,
        )
        for step in timeline.steps
    ] == [
        ("v1", "v2"),
        ("v2", "v3"),
    ]

    assert timeline.has_branches is False
    assert timeline.branch_point_ids == []
    assert timeline.leaf_version_ids == [
        "v3"
    ]


def test_branching_lineage_is_not_flattened():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
            reason="initial_research",
        ),
        lineage(
            research_id="v2_a",
            root="v1",
            parent="v1",
            version=2,
        ),
        lineage(
            research_id="v2_b",
            root="v1",
            parent="v1",
            version=2,
        ),
    ]

    states = {
        "v1": state("v1"),
        "v2_a": state("v2 a"),
        "v2_b": state("v2 b"),
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    assert timeline.has_branches is True

    assert (
        timeline.branch_point_ids
        == ["v1"]
    )

    edges = {
        (
            step.source_research_id,
            step.target_research_id,
        )
        for step in timeline.steps
    }

    assert edges == {
        ("v1", "v2_a"),
        ("v1", "v2_b"),
    }

    # Critical:
    # siblings must never be compared as
    # v2_a -> v2_b.
    assert (
        ("v2_a", "v2_b")
        not in edges
    )


def test_branch_child_keeps_correct_parent():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2_a",
            root="v1",
            parent="v1",
            version=2,
        ),
        lineage(
            research_id="v2_b",
            root="v1",
            parent="v1",
            version=2,
        ),
        lineage(
            research_id="v3_b",
            root="v1",
            parent="v2_b",
            version=3,
        ),
    ]

    states = {
        item.research_id: state(
            item.research_id
        )
        for item in items
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    edges = [
        (
            step.source_research_id,
            step.target_research_id,
        )
        for step in timeline.steps
    ]

    assert (
        "v2_b",
        "v3_b",
    ) in edges

    assert (
        "v2_a",
        "v3_b",
    ) not in edges


def test_creation_reason_and_trigger_provenance_preserved():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
            reason="reevaluation",
            triggers=[
                "trigger_security",
                "trigger_price",
            ],
        ),
    ]

    states = {
        "v1": state("v1"),
        "v2": state("v2"),
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    step = timeline.steps[0]

    assert (
        step.target_creation_reason
        == "reevaluation"
    )

    assert (
        step.created_from_trigger_ids
        == [
            "trigger_security",
            "trigger_price",
        ]
    )


def test_missing_state_skips_edge_without_synthetic_diff():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
        ),
    ]

    states = {
        "v1": state("v1"),
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    assert timeline.steps == []


def test_missing_parent_metadata_skips_edge():
    items = [
        lineage(
            research_id="orphan",
            root="root",
            parent="missing_parent",
            version=2,
        )
    ]

    states = {
        "orphan": state("orphan"),
    }

    timeline = build_decision_evolution(
        root_research_id="root",
        lineage_items=items,
        load_state=states.get,
    )

    assert timeline.steps == []


def test_other_root_items_are_ignored():
    items = [
        lineage(
            research_id="a1",
            root="a1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="b1",
            root="b1",
            parent=None,
            version=1,
        ),
    ]

    states = {
        "a1": state("a"),
        "b1": state("b"),
    }

    timeline = build_decision_evolution(
        root_research_id="a1",
        lineage_items=items,
        load_state=states.get,
    )

    assert timeline.research_ids == [
        "a1"
    ]


def test_step_reuses_phase41_diff():
    before = state("before")
    after = state("after")

    before.evidence_items = []
    after.evidence_items = []

    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
        ),
    ]

    states = {
        "v1": before,
        "v2": after,
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    step = timeline.steps[0]

    assert (
        step.diff.source_research_id
        == "v1"
    )

    assert (
        step.diff.target_research_id
        == "v2"
    )


def test_evolution_contains_no_quality_judgment_fields():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
        ),
    ]

    states = {
        "v1": state("v1"),
        "v2": state("v2"),
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    forbidden = {
        "better_version",
        "preferred_version",
        "improved",
        "winner",
        "quality_change",
    }

    assert not (
        forbidden
        & set(vars(timeline))
    )

    assert not (
        forbidden
        & set(vars(timeline.steps[0]))
    )


def test_evolution_step_contains_deterministic_attribution():
    before = state("before")
    after = state("after")

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

    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
        ),
    ]

    states = {
        "v1": before,
        "v2": after,
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    step = timeline.steps[0]

    assert (
        step.attribution.source_research_id
        == "v1"
    )

    assert (
        step.attribution.target_research_id
        == "v2"
    )

    evidence_group = next(
        group
        for group in step.attribution.groups
        if group.section == "evidence"
    )

    assert evidence_group.added_count == 1

    assert (
        evidence_group.items[0].field_name
        == "evidence.ev_new"
    )


def test_attribution_is_projection_of_same_step_diff():
    before = state("before")
    after = state("after")

    before.evidence_items = []
    after.evidence_items = []

    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
        ),
    ]

    states = {
        "v1": before,
        "v2": after,
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    step = timeline.steps[0]

    assert (
        step.attribution.has_changes
        == step.diff.has_changes
    )

    assert (
        step.attribution.source_research_id
        == step.diff.source_research_id
    )

    assert (
        step.attribution.target_research_id
        == step.diff.target_research_id
    )


def test_evolution_attribution_has_no_causal_or_quality_fields():
    items = [
        lineage(
            research_id="v1",
            root="v1",
            parent=None,
            version=1,
        ),
        lineage(
            research_id="v2",
            root="v1",
            parent="v1",
            version=2,
        ),
    ]

    states = {
        "v1": state("v1"),
        "v2": state("v2"),
    }

    timeline = build_decision_evolution(
        root_research_id="v1",
        lineage_items=items,
        load_state=states.get,
    )

    attribution = (
        timeline.steps[0].attribution
    )

    forbidden = {
        "cause",
        "caused_by",
        "causal_effect",
        "better_version",
        "preferred_version",
        "preferred_branch",
        "improvement",
        "winner",
    }

    assert not (
        forbidden
        & set(vars(attribution))
    )

    for group in attribution.groups:
        assert not (
            forbidden
            & set(vars(group))
        )
