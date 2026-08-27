from types import SimpleNamespace

from models import SummaryState
from services.decision_version_diff import (
    ADDED,
    CHANGED,
    REMOVED,
    compare_research_versions,
)


def ns(**kwargs):
    return SimpleNamespace(**kwargs)


def make_state():
    return SummaryState(
        research_topic="vector db decision",
        evidence_items=[],
        decision_assumptions=[],
        decision_reevaluation_triggers=[],
        integration_assessments=[],
    )


def test_identical_versions_have_no_changes():
    before = make_state()
    after = make_state()

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert diff.has_changes is False

    assert set(
        diff.unchanged_sections
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


def test_authoritative_recommendation_change_is_reported():
    before = make_state()
    after = make_state()

    before.decision_case = ns(
        decision_id="decision_1",
        question="Which database?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[],
        recommendation=None,
    )

    after.decision_case = ns(
        decision_id="decision_1",
        question="Which database?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[],
        recommendation="Choose Qdrant.",
    )

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert len(
        diff.recommendation_changes
    ) == 1

    change = (
        diff.recommendation_changes[0]
    )

    assert (
        change.field_name
        == "decision_case.recommendation"
    )

    assert change.change_type == ADDED
    assert change.before is None
    assert change.after == "Choose Qdrant."


def test_comparison_winner_is_not_treated_as_recommendation():
    before = make_state()
    after = make_state()

    before.decision_case = ns(
        decision_id="decision_1",
        question="Which database?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[],
        recommendation=None,
    )

    after.decision_case = ns(
        decision_id="decision_1",
        question="Which database?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[],
        recommendation=None,
    )

    before.decision_comparison = ns(
        ranked_candidates=[
            ns(
                candidate_id="a",
                rank=1,
            )
        ]
    )

    after.decision_comparison = ns(
        ranked_candidates=[
            ns(
                candidate_id="b",
                rank=1,
            )
        ]
    )

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert (
        diff.recommendation_changes
        == []
    )


def test_readiness_change_uses_persisted_values_only():
    before = make_state()
    after = make_state()

    before.decision_readiness = ns(
        status="TENTATIVE",
        overall_score=0.52,
        criterion_coverage=0.5,
        evidence_quality=0.6,
        applicability=0.7,
        agreement_score=0.5,
        decision_margin=0.1,
        blocking_reasons=[
            "missing evidence",
        ],
        research_gap_ids=[
            "gap_1",
        ],
    )

    after.decision_readiness = ns(
        status="READY",
        overall_score=0.82,
        criterion_coverage=0.9,
        evidence_quality=0.8,
        applicability=0.8,
        agreement_score=0.8,
        decision_margin=0.3,
        blocking_reasons=[],
        research_gap_ids=[],
    )

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    names = {
        change.field_name
        for change
        in diff.readiness_changes
    }

    assert "status" in names
    assert "overall_score" in names
    assert "research_gap_ids" in names


def test_added_and_removed_evidence_are_explicit():
    before = make_state()
    after = make_state()

    before.evidence_items = [
        ns(
            evidence_id="ev_old",
            content="old",
        ),
    ]

    after.evidence_items = [
        ns(
            evidence_id="ev_new",
            content="new",
        ),
    ]

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    changes = {
        change.field_name:
            change.change_type
        for change
        in diff.evidence_changes
    }

    assert (
        changes["evidence.ev_old"]
        == REMOVED
    )

    assert (
        changes["evidence.ev_new"]
        == ADDED
    )


def test_changed_evidence_same_id_is_changed_not_new():
    before = make_state()
    after = make_state()

    before.evidence_items = [
        ns(
            evidence_id="ev_1",
            content="before",
        ),
    ]

    after.evidence_items = [
        ns(
            evidence_id="ev_1",
            content="after",
        ),
    ]

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert len(
        diff.evidence_changes
    ) == 1

    assert (
        diff.evidence_changes[
            0
        ].change_type
        == CHANGED
    )


def test_research_gap_changes_use_gap_id():
    before = make_state()
    after = make_state()

    before.research_analysis = ns(
        research_gaps=[
            ns(
                gap_id="gap_1",
                status="open",
            ),
        ]
    )

    after.research_analysis = ns(
        research_gaps=[
            ns(
                gap_id="gap_1",
                status="resolved",
            ),
            ns(
                gap_id="gap_2",
                status="open",
            ),
        ]
    )

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    changes = {
        change.field_name:
            change.change_type
        for change
        in diff.research_gap_changes
    }

    assert (
        changes["research_gap.gap_1"]
        == CHANGED
    )

    assert (
        changes["research_gap.gap_2"]
        == ADDED
    )


def test_assumptions_and_triggers_are_separate():
    before = make_state()
    after = make_state()

    before.decision_assumptions = [
        ns(
            assumption_id="assumption_1",
            status="active",
        ),
    ]

    after.decision_assumptions = [
        ns(
            assumption_id="assumption_1",
            status="changed",
        ),
    ]

    before.decision_reevaluation_triggers = [
        ns(
            trigger_id="trigger_1",
            status="inactive",
        ),
    ]

    after.decision_reevaluation_triggers = [
        ns(
            trigger_id="trigger_1",
            status="active",
        ),
    ]

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert len(
        diff.assumption_changes
    ) == 1

    assert len(
        diff.trigger_changes
    ) == 1


def test_hard_constraints_remain_decision_changes_not_assumptions():
    before = make_state()
    after = make_state()

    before.decision_case = ns(
        decision_id="decision_1",
        question="Which database?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[
            ns(
                constraint_id="constraint_1",
                text="Must be self-hosted",
            )
        ],
        recommendation=None,
    )

    after.decision_case = ns(
        decision_id="decision_1",
        question="Which database?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[
            ns(
                constraint_id="constraint_1",
                text="Must support EU hosting",
            )
        ],
        recommendation=None,
    )

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert any(
        change.field_name
        == "constraint.constraint_1"
        for change
        in diff.decision_changes
    )

    assert (
        diff.assumption_changes
        == []
    )


def test_architecture_changes_are_structural_only():
    before = make_state()
    after = make_state()

    before.technical_context = ns(
        deployment="single region",
    )

    after.technical_context = ns(
        deployment="multi region",
    )

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert len(
        diff.architecture_changes
    ) == 1

    change = (
        diff.architecture_changes[0]
    )

    assert (
        change.field_name
        == "technical_context"
    )

    assert (
        change.change_type
        == CHANGED
    )


def test_inputs_are_not_mutated():
    before = make_state()
    after = make_state()

    before.evidence_items = [
        ns(
            evidence_id="ev_1",
            content="before",
        )
    ]

    after.evidence_items = [
        ns(
            evidence_id="ev_2",
            content="after",
        )
    ]

    before_snapshot = [
        item.evidence_id
        for item
        in before.evidence_items
    ]

    after_snapshot = [
        item.evidence_id
        for item
        in after.evidence_items
    ]

    compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert [
        item.evidence_id
        for item
        in before.evidence_items
    ] == before_snapshot

    assert [
        item.evidence_id
        for item
        in after.evidence_items
    ] == after_snapshot


def test_summary_is_empty_quality_judgment_free():
    before = make_state()
    after = make_state()

    after.evidence_items = [
        ns(
            evidence_id="ev_1",
            content="new",
        )
    ]

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert diff.summary_lines == [
        "Evidence: 1 added"
    ]

    text = " ".join(
        diff.summary_lines
    ).lower()

    forbidden = (
        "better",
        "improved",
        "superior",
        "more accurate",
        "best",
    )

    assert not any(
        word in text
        for word in forbidden
    )


def test_summary_reports_multiple_structural_sections():
    before = make_state()
    after = make_state()

    before.decision_case = ns(
        decision_id="decision_1",
        question="Which?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[],
        recommendation=None,
    )

    after.decision_case = ns(
        decision_id="decision_1",
        question="Which?",
        candidates=[],
        criteria=[],
        requirements=[],
        constraints=[],
        recommendation="Choose A.",
    )

    after.evidence_items = [
        ns(
            evidence_id="ev_1",
            content="new",
        )
    ]

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert (
        "Recommendation: 1 added"
        in diff.summary_lines
    )

    assert (
        "Evidence: 1 added"
        in diff.summary_lines
    )


def test_identical_version_summary_is_explicit():
    before = make_state()
    after = make_state()

    diff = compare_research_versions(
        source_research_id="research_v1",
        source_state=before,
        target_research_id="research_v2",
        target_state=after,
    )

    assert diff.summary_lines == [
        "No tracked structural changes were detected."
    ]
