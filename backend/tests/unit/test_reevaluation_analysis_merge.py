import pytest

from models import (
    CriterionCoverage,
    EvidenceConflict,
    ResearchAnalysis,
    ResearchGap,
)
from services.reevaluation_analysis_merge import (
    merge_reevaluation_research_gaps,
)


def existing_gap(
    *,
    gap_id="gap_existing",
):
    return ResearchGap(
        gap_id=gap_id,
        candidate_id="cand_a",
        criterion_id="crit_ops",
        gap_type="low_coverage",
        severity=0.8,
        description="Existing research gap",
        suggested_query="existing query",
        status="open",
    )


def reevaluation_gap(
    *,
    gap_id="gap_reeval",
    query="updated deployment evidence",
):
    return ResearchGap(
        gap_id=gap_id,
        candidate_id="",
        criterion_id="",
        gap_type="reevaluation",
        severity=1.0,
        description=(
            "Re-evaluate stale deployment state"
        ),
        suggested_query=query,
        status="open",
        priority=3,
    )


def analysis(
    *,
    gaps=None,
    status="gaps_detected",
):
    coverage = CriterionCoverage(
        candidate_id="cand_a",
        criterion_id="crit_ops",
        signal_count=1,
        effective_signal_count=1,
        coverage_score=0.5,
        confidence_score=0.6,
    )

    conflict = EvidenceConflict(
        candidate_id="cand_a",
        criterion_id="crit_ops",
        conflict_score=0.0,
        resolution_status="none",
    )

    return ResearchAnalysis(
        decision_id="dec_test",
        coverages=[
            coverage,
        ],
        conflicts=[
            conflict,
        ],
        research_gaps=(
            [existing_gap()]
            if gaps is None
            else gaps
        ),
        status=status,
    )


def test_appends_reevaluation_gap_after_existing_gaps():
    original = analysis()
    reeval = reevaluation_gap()

    merged = merge_reevaluation_research_gaps(
        original,
        [reeval],
    )

    assert [
        gap.gap_id
        for gap in merged.research_gaps
    ] == [
        "gap_existing",
        "gap_reeval",
    ]


def test_existing_gap_object_is_preserved():
    original = analysis()

    existing = original.research_gaps[0]

    merged = merge_reevaluation_research_gaps(
        original,
        [
            reevaluation_gap(),
        ],
    )

    assert (
        merged.research_gaps[0]
        is existing
    )


def test_reevaluation_gap_object_is_preserved():
    original = analysis()
    reeval = reevaluation_gap()

    merged = merge_reevaluation_research_gaps(
        original,
        [reeval],
    )

    assert (
        merged.research_gaps[-1]
        is reeval
    )


def test_existing_gap_wins_on_id_collision():
    original_gap = existing_gap(
        gap_id="gap_same"
    )

    original = analysis(
        gaps=[
            original_gap,
        ],
    )

    reeval = reevaluation_gap(
        gap_id="gap_same",
    )

    merged = merge_reevaluation_research_gaps(
        original,
        [reeval],
    )

    assert merged is original

    assert merged.research_gaps == [
        original_gap,
    ]

    assert (
        merged.research_gaps[0].gap_type
        == "low_coverage"
    )


def test_duplicate_reevaluation_input_is_deduplicated():
    first = reevaluation_gap(
        gap_id="gap_same"
    )

    second = reevaluation_gap(
        gap_id="gap_same",
        query="different query",
    )

    merged = merge_reevaluation_research_gaps(
        analysis(),
        [
            first,
            second,
        ],
    )

    matching = [
        gap
        for gap in merged.research_gaps
        if gap.gap_id == "gap_same"
    ]

    assert matching == [
        first,
    ]


def test_merge_preserves_coverage_and_conflict_objects():
    original = analysis()

    coverage = original.coverages[0]
    conflict = original.conflicts[0]

    merged = merge_reevaluation_research_gaps(
        original,
        [
            reevaluation_gap(),
        ],
    )

    assert merged.coverages == (
        original.coverages
    )

    assert merged.conflicts == (
        original.conflicts
    )

    assert merged.coverages[0] is coverage
    assert merged.conflicts[0] is conflict


def test_merge_does_not_mutate_original_analysis():
    original = analysis()

    before = list(
        original.research_gaps
    )

    merged = merge_reevaluation_research_gaps(
        original,
        [
            reevaluation_gap(),
        ],
    )

    assert merged is not original

    assert (
        original.research_gaps
        == before
    )

    assert [
        gap.gap_id
        for gap in original.research_gaps
    ] == [
        "gap_existing",
    ]


def test_merge_does_not_mutate_input_gap_list():
    original = analysis()

    reevals = [
        reevaluation_gap(),
    ]

    before = list(
        reevals
    )

    merge_reevaluation_research_gaps(
        original,
        reevals,
    )

    assert reevals == before


def test_new_gap_changes_complete_analysis_to_gaps_detected():
    original = analysis(
        gaps=[],
        status="complete",
    )

    merged = merge_reevaluation_research_gaps(
        original,
        [
            reevaluation_gap(),
        ],
    )

    assert (
        merged.status
        == "gaps_detected"
    )


def test_no_additions_preserve_original_analysis_exactly():
    existing = reevaluation_gap()

    original = analysis(
        gaps=[
            existing,
        ],
        status="gaps_detected",
    )

    merged = merge_reevaluation_research_gaps(
        original,
        [
            reevaluation_gap(),
        ],
    )

    assert merged is original


def test_created_at_is_preserved():
    original = analysis()

    created_at = original.created_at

    merged = merge_reevaluation_research_gaps(
        original,
        [
            reevaluation_gap(),
        ],
    )

    assert merged.created_at == created_at


def test_non_reevaluation_gap_is_rejected():
    wrong = existing_gap(
        gap_id="gap_wrong"
    )

    with pytest.raises(
        ValueError,
        match="gap_type='reevaluation'",
    ):
        merge_reevaluation_research_gaps(
            analysis(),
            [
                wrong,
            ],
        )


def test_merge_does_not_create_decision_outputs():
    merged = merge_reevaluation_research_gaps(
        analysis(),
        [
            reevaluation_gap(),
        ],
    )

    assert not hasattr(
        merged,
        "candidate_scores",
    )

    assert not hasattr(
        merged,
        "recommendation",
    )

    assert not hasattr(
        merged,
        "predicted_winner_id",
    )
