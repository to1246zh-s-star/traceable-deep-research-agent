import pytest

from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    EvidenceSignal,
)
from services.research_analysis import (
    analyze_research,
    calculate_coverage,
    detect_conflict,
    signal_effective_weight,
)


def build_decision():
    qdrant = Candidate(name="Qdrant")
    milvus = Candidate(name="Milvus")

    reliability = DecisionCriterion(
        name="Reliability",
        weight=0.5,
    )

    performance = DecisionCriterion(
        name="Performance",
        weight=0.5,
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[
            qdrant,
            milvus,
        ],
        criteria=[
            reliability,
            performance,
        ],
    )

    return (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    )


def make_signal(
    *,
    evidence_id,
    candidate_id,
    criterion_id,
    direction="positive",
    strength=1.0,
    source_confidence=1.0,
    applicability=1.0,
):
    return EvidenceSignal(
        evidence_id=evidence_id,
        candidate_id=candidate_id,
        criterion_id=criterion_id,
        direction=direction,
        strength=strength,
        source_confidence=source_confidence,
        applicability=applicability,
    )


def test_signal_effective_weight_combines_three_dimensions():
    signal = make_signal(
        evidence_id="evi_1",
        candidate_id="cand_1",
        criterion_id="crit_1",
        strength=0.8,
        source_confidence=0.9,
        applicability=0.5,
    )

    assert signal_effective_weight(signal) == pytest.approx(
        0.8 * 0.9 * 0.5
    )


def test_two_strong_signals_produce_full_coverage():
    (
        _,
        qdrant,
        _,
        reliability,
        _,
    ) = build_decision()

    signals = [
        make_signal(
            evidence_id="evi_1",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
        ),
        make_signal(
            evidence_id="evi_2",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
        ),
    ]

    coverage = calculate_coverage(
        qdrant.candidate_id,
        reliability.criterion_id,
        signals,
    )

    assert coverage.signal_count == 2
    assert coverage.effective_signal_count == pytest.approx(2.0)
    assert coverage.coverage_score == pytest.approx(1.0)
    assert coverage.confidence_score == pytest.approx(1.0)


def test_low_applicability_reduces_coverage():
    (
        _,
        qdrant,
        _,
        reliability,
        _,
    ) = build_decision()

    signals = [
        make_signal(
            evidence_id="evi_1",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            applicability=0.2,
        )
    ]

    coverage = calculate_coverage(
        qdrant.candidate_id,
        reliability.criterion_id,
        signals,
    )

    assert coverage.coverage_score == pytest.approx(0.1)
    assert coverage.confidence_score == pytest.approx(0.2)


def test_balanced_positive_and_negative_signals_create_conflict():
    (
        _,
        qdrant,
        _,
        reliability,
        _,
    ) = build_decision()

    positive = make_signal(
        evidence_id="evi_positive",
        candidate_id=qdrant.candidate_id,
        criterion_id=reliability.criterion_id,
        direction="positive",
    )

    negative = make_signal(
        evidence_id="evi_negative",
        candidate_id=qdrant.candidate_id,
        criterion_id=reliability.criterion_id,
        direction="negative",
    )

    conflict = detect_conflict(
        qdrant.candidate_id,
        reliability.criterion_id,
        [
            positive,
            negative,
        ],
    )

    assert conflict.conflict_score == pytest.approx(1.0)
    assert conflict.resolution_status == "unresolved"

    assert conflict.supporting_signal_ids == [
        positive.signal_id
    ]

    assert conflict.opposing_signal_ids == [
        negative.signal_id
    ]


def test_one_sided_evidence_has_no_conflict():
    (
        _,
        qdrant,
        _,
        reliability,
        _,
    ) = build_decision()

    signal = make_signal(
        evidence_id="evi_positive",
        candidate_id=qdrant.candidate_id,
        criterion_id=reliability.criterion_id,
        direction="positive",
    )

    conflict = detect_conflict(
        qdrant.candidate_id,
        reliability.criterion_id,
        [signal],
    )

    assert conflict.conflict_score == 0.0
    assert conflict.resolution_status == "none"


def test_missing_candidate_criterion_evidence_creates_gap():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    ) = build_decision()

    signals = [
        make_signal(
            evidence_id="evi_1",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
        ),
        make_signal(
            evidence_id="evi_2",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
        ),
    ]

    analysis = analyze_research(
        decision,
        signals,
    )

    missing_pairs = {
        (
            gap.candidate_id,
            gap.criterion_id,
        )
        for gap in analysis.research_gaps
        if gap.gap_type == "missing_evidence"
    }

    assert (
        qdrant.candidate_id,
        performance.criterion_id,
    ) in missing_pairs

    assert (
        milvus.candidate_id,
        reliability.criterion_id,
    ) in missing_pairs

    assert (
        milvus.candidate_id,
        performance.criterion_id,
    ) in missing_pairs


def test_low_quality_signal_creates_low_coverage_and_weak_source_gap():
    (
        decision,
        qdrant,
        _,
        reliability,
        _,
    ) = build_decision()

    signals = [
        make_signal(
            evidence_id="evi_weak",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            strength=0.5,
            source_confidence=0.4,
            applicability=0.4,
        )
    ]

    analysis = analyze_research(
        decision,
        signals,
    )

    pair_gaps = [
        gap
        for gap in analysis.research_gaps
        if (
            gap.candidate_id == qdrant.candidate_id
            and gap.criterion_id == reliability.criterion_id
        )
    ]

    gap_types = {
        gap.gap_type
        for gap in pair_gaps
    }

    assert "low_coverage" in gap_types
    assert "weak_source" in gap_types


def test_conflicting_evidence_creates_research_gap():
    (
        decision,
        qdrant,
        _,
        reliability,
        _,
    ) = build_decision()

    signals = [
        make_signal(
            evidence_id="evi_positive",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            direction="positive",
        ),
        make_signal(
            evidence_id="evi_negative",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            direction="negative",
        ),
    ]

    analysis = analyze_research(
        decision,
        signals,
    )

    conflict_gaps = [
        gap
        for gap in analysis.research_gaps
        if (
            gap.candidate_id == qdrant.candidate_id
            and gap.criterion_id == reliability.criterion_id
            and gap.gap_type == "conflicting_evidence"
        )
    ]

    assert len(conflict_gaps) == 1
    assert conflict_gaps[0].severity == pytest.approx(1.0)


def test_complete_strong_coverage_can_have_no_gap_for_pair():
    candidate = Candidate(name="Qdrant")

    criterion = DecisionCriterion(
        name="Reliability",
        weight=1.0,
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[candidate],
        criteria=[criterion],
    )

    signals = [
        make_signal(
            evidence_id="evi_1",
            candidate_id=candidate.candidate_id,
            criterion_id=criterion.criterion_id,
        ),
        make_signal(
            evidence_id="evi_2",
            candidate_id=candidate.candidate_id,
            criterion_id=criterion.criterion_id,
        ),
    ]

    analysis = analyze_research(
        decision,
        signals,
    )

    assert analysis.status == "complete"
    assert analysis.research_gaps == []


@pytest.mark.parametrize(
    "direction",
    [
        "support",
        "opposing",
        "yes",
    ],
)
def test_invalid_signal_direction_is_rejected(direction):
    (
        decision,
        qdrant,
        _,
        reliability,
        _,
    ) = build_decision()

    signal = make_signal(
        evidence_id="evi_bad",
        candidate_id=qdrant.candidate_id,
        criterion_id=reliability.criterion_id,
        direction=direction,
    )

    with pytest.raises(
        ValueError,
        match="invalid signal direction",
    ):
        analyze_research(
            decision,
            [signal],
        )


def test_research_gaps_include_suggested_query():
    (
        decision,
        _,
        _,
        _,
        _,
    ) = build_decision()

    analysis = analyze_research(
        decision,
        [],
    )

    assert analysis.research_gaps

    assert all(
        gap.suggested_query
        for gap in analysis.research_gaps
    )
