from services.decision_change_attribution import (
    build_change_attribution,
)
from services.decision_version_diff import (
    ADDED,
    CHANGED,
    REMOVED,
    DecisionVersionDiff,
    VersionFieldChange,
)


def change(
    *,
    field_name: str,
    change_type: str,
    before=None,
    after=None,
):
    return VersionFieldChange(
        field_name=field_name,
        change_type=change_type,
        before=before,
        after=after,
    )


def empty_diff():
    return DecisionVersionDiff(
        source_research_id="v1",
        target_research_id="v2",
        has_changes=False,
    )


def group_by_section(
    attribution,
):
    return {
        group.section: group
        for group in attribution.groups
    }


def test_empty_diff_produces_explicit_unchanged_groups():
    attribution = build_change_attribution(
        empty_diff()
    )

    assert attribution.has_changes is False
    assert attribution.changed_sections == []

    assert set(
        attribution.unchanged_sections
    ) == {
        "decision",
        "readiness",
        "recommendation",
        "research_gaps",
        "evidence",
        "assumptions",
        "reevaluation_triggers",
        "architecture",
    }

    assert len(
        attribution.groups
    ) == 8


def test_evidence_changes_are_attributed_to_evidence_group():
    diff = empty_diff()

    diff.has_changes = True
    diff.evidence_changes = [
        change(
            field_name="evidence.ev_1",
            change_type=ADDED,
            after={
                "evidence_id": "ev_1",
            },
        ),
        change(
            field_name="evidence.ev_2",
            change_type=CHANGED,
            before={
                "content": "before",
            },
            after={
                "content": "after",
            },
        ),
    ]

    attribution = build_change_attribution(
        diff
    )

    group = group_by_section(
        attribution
    )["evidence"]

    assert group.has_changes is True
    assert group.added_count == 1
    assert group.changed_count == 1
    assert group.removed_count == 0

    assert [
        item.field_name
        for item in group.items
    ] == [
        "evidence.ev_1",
        "evidence.ev_2",
    ]


def test_research_gap_added_removed_changed_are_counted_separately():
    diff = empty_diff()

    diff.has_changes = True
    diff.research_gap_changes = [
        change(
            field_name="research_gap.gap_1",
            change_type=ADDED,
        ),
        change(
            field_name="research_gap.gap_2",
            change_type=REMOVED,
        ),
        change(
            field_name="research_gap.gap_3",
            change_type=CHANGED,
        ),
    ]

    group = group_by_section(
        build_change_attribution(
            diff
        )
    )["research_gaps"]

    assert group.added_count == 1
    assert group.removed_count == 1
    assert group.changed_count == 1


def test_hard_constraint_change_stays_in_decision_group():
    diff = empty_diff()

    diff.has_changes = True
    diff.decision_changes = [
        change(
            field_name="constraint.constraint_1",
            change_type=CHANGED,
            before={
                "text": "Must be self-hosted",
            },
            after={
                "text": "Must support EU hosting",
            },
        )
    ]

    attribution = (
        build_change_attribution(
            diff
        )
    )

    groups = group_by_section(
        attribution
    )

    assert (
        groups["decision"]
        .items[0]
        .field_name
        == "constraint.constraint_1"
    )

    assert (
        groups["assumptions"]
        .items
        == []
    )


def test_recommendation_change_is_kept_separate():
    diff = empty_diff()

    diff.has_changes = True
    diff.recommendation_changes = [
        change(
            field_name=(
                "decision_case.recommendation"
            ),
            change_type=ADDED,
            before=None,
            after="Choose A.",
        )
    ]

    attribution = build_change_attribution(
        diff
    )

    group = group_by_section(
        attribution
    )["recommendation"]

    assert len(group.items) == 1

    assert (
        group.items[0].field_name
        == "decision_case.recommendation"
    )


def test_readiness_change_is_not_interpreted_as_improvement():
    diff = empty_diff()

    diff.has_changes = True
    diff.readiness_changes = [
        change(
            field_name="status",
            change_type=CHANGED,
            before="TENTATIVE",
            after="READY",
        )
    ]

    attribution = build_change_attribution(
        diff
    )

    group = group_by_section(
        attribution
    )["readiness"]

    assert group.changed_count == 1

    serialized_names = {
        key
        for key in vars(
            attribution
        )
    }

    forbidden = {
        "improved",
        "improvement",
        "better_version",
        "quality_change",
        "preferred_version",
    }

    assert not (
        serialized_names
        & forbidden
    )


def test_trigger_changes_remain_trigger_structure_not_causality():
    diff = empty_diff()

    diff.has_changes = True
    diff.trigger_changes = [
        change(
            field_name=(
                "reevaluation_trigger.trigger_1"
            ),
            change_type=CHANGED,
            before={
                "status": "inactive",
            },
            after={
                "status": "active",
            },
        )
    ]

    attribution = build_change_attribution(
        diff
    )

    group = group_by_section(
        attribution
    )[
        "reevaluation_triggers"
    ]

    assert len(group.items) == 1

    forbidden = {
        "caused_by",
        "cause",
        "causal_effect",
        "decision_driver",
    }

    assert not (
        forbidden
        & set(vars(group))
    )


def test_architecture_change_preserves_before_after():
    diff = empty_diff()

    diff.has_changes = True
    diff.architecture_changes = [
        change(
            field_name="technical_context",
            change_type=CHANGED,
            before={
                "deployment": "single-region",
            },
            after={
                "deployment": "multi-region",
            },
        )
    ]

    group = group_by_section(
        build_change_attribution(
            diff
        )
    )["architecture"]

    item = group.items[0]

    assert item.before == {
        "deployment": "single-region",
    }

    assert item.after == {
        "deployment": "multi-region",
    }


def test_section_order_is_deterministic():
    attribution = build_change_attribution(
        empty_diff()
    )

    assert [
        group.section
        for group in attribution.groups
    ] == [
        "decision",
        "readiness",
        "recommendation",
        "research_gaps",
        "evidence",
        "assumptions",
        "reevaluation_triggers",
        "architecture",
    ]


def test_source_diff_is_not_mutated():
    diff = empty_diff()

    diff.has_changes = True
    diff.evidence_changes = [
        change(
            field_name="evidence.ev_1",
            change_type=ADDED,
        )
    ]

    before = list(
        diff.evidence_changes
    )

    build_change_attribution(
        diff
    )

    assert (
        diff.evidence_changes
        == before
    )
