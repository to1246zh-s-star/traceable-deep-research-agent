import pytest

from models import (
    Candidate,
    CandidateWeightedScore,
    CriterionCoverage,
    DecisionCase,
    DecisionComparison,
    DecisionCriterion,
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceConflict,
    EvidenceQuality,
    ResearchAnalysis,
    SourceQuality,
)
from services.decision_readiness import (
    aggregate_agreement,
    calculate_decision_margin,
    calculate_readiness,
)


def make_decision():
    qdrant = Candidate(name="Qdrant")
    milvus = Candidate(name="Milvus")

    reliability = DecisionCriterion(
        name="Reliability",
        weight=0.6,
    )

    performance = DecisionCriterion(
        name="Performance",
        weight=0.4,
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


def make_assessment(
    decision_id,
    evidence_id,
    *,
    source_confidence=1.0,
    quality=1.0,
    applicability=1.0,
):
    return EvidenceAssessment(
        evidence_id=evidence_id,
        decision_id=decision_id,
        source_quality=SourceQuality(
            evidence_id=evidence_id,
            source_type="official_docs",
            confidence=source_confidence,
        ),
        evidence_quality=EvidenceQuality(
            evidence_id=evidence_id,
            quality_score=quality,
            completeness=quality,
        ),
        applicability=EvidenceApplicability(
            evidence_id=evidence_id,
            decision_id=decision_id,
            applicability_score=applicability,
        ),
        overall_score=(
            source_confidence
            * quality
            * applicability
        ),
    )


def make_complete_comparison(
    decision,
    qdrant,
    milvus,
    *,
    qdrant_score=9.0,
    milvus_score=7.0,
):
    return DecisionComparison(
        decision_id=decision.decision_id,
        status="complete",
        candidate_scores=[
            CandidateWeightedScore(
                candidate_id=qdrant.candidate_id,
                weighted_score=qdrant_score,
                rank=1,
            ),
            CandidateWeightedScore(
                candidate_id=milvus.candidate_id,
                weighted_score=milvus_score,
                rank=2,
            ),
        ],
        ranked_candidate_ids=[
            qdrant.candidate_id,
            milvus.candidate_id,
        ],
    )


def make_strong_analysis(
    decision,
    qdrant,
    milvus,
    reliability,
    performance,
):
    coverages = []

    for candidate in [
        qdrant,
        milvus,
    ]:
        for criterion in [
            reliability,
            performance,
        ]:
            coverages.append(
                CriterionCoverage(
                    candidate_id=candidate.candidate_id,
                    criterion_id=criterion.criterion_id,
                    signal_count=2,
                    effective_signal_count=2.0,
                    coverage_score=1.0,
                    confidence_score=1.0,
                )
            )

    return ResearchAnalysis(
        decision_id=decision.decision_id,
        coverages=coverages,
        conflicts=[],
        research_gaps=[],
        status="complete",
    )


def test_decision_margin_uses_top_two_candidates():
    (
        decision,
        qdrant,
        milvus,
        _,
        _,
    ) = make_decision()

    comparison = make_complete_comparison(
        decision,
        qdrant,
        milvus,
        qdrant_score=9.0,
        milvus_score=7.0,
    )

    assert calculate_decision_margin(
        comparison
    ) == pytest.approx(0.2)


def test_single_candidate_has_maximum_margin():
    (
        decision,
        qdrant,
        _,
        _,
        _,
    ) = make_decision()

    comparison = DecisionComparison(
        decision_id=decision.decision_id,
        status="complete",
        candidate_scores=[
            CandidateWeightedScore(
                candidate_id=qdrant.candidate_id,
                weighted_score=8.0,
                rank=1,
            )
        ],
        ranked_candidate_ids=[
            qdrant.candidate_id
        ],
    )

    assert calculate_decision_margin(
        comparison
    ) == pytest.approx(1.0)


def test_no_conflict_means_full_agreement():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    ) = make_decision()

    analysis = make_strong_analysis(
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    )

    assert aggregate_agreement(
        analysis
    ) == pytest.approx(1.0)


def test_high_quality_complete_decision_can_be_ready():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    ) = make_decision()

    comparison = make_complete_comparison(
        decision,
        qdrant,
        milvus,
        qdrant_score=10.0,
        milvus_score=0.0,
    )

    analysis = make_strong_analysis(
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    )

    assessments = [
        make_assessment(
            decision.decision_id,
            "evi_1",
        ),
        make_assessment(
            decision.decision_id,
            "evi_2",
        ),
    ]

    readiness = calculate_readiness(
        decision,
        comparison,
        analysis,
        assessments,
    )

    assert readiness.status == "READY"
    assert readiness.overall_score >= 0.75
    assert readiness.blocking_reasons == []


def test_low_readiness_returns_insufficient_evidence():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    ) = make_decision()

    comparison = make_complete_comparison(
        decision,
        qdrant,
        milvus,
        qdrant_score=5.1,
        milvus_score=5.0,
    )

    analysis = ResearchAnalysis(
        decision_id=decision.decision_id,
        coverages=[
            CriterionCoverage(
                candidate_id=qdrant.candidate_id,
                criterion_id=reliability.criterion_id,
                signal_count=1,
                effective_signal_count=0.2,
                coverage_score=0.1,
                confidence_score=0.2,
            )
        ],
        conflicts=[],
        research_gaps=[],
    )

    assessments = [
        make_assessment(
            decision.decision_id,
            "evi_weak",
            source_confidence=0.4,
            quality=0.4,
            applicability=0.4,
        )
    ]

    readiness = calculate_readiness(
        decision,
        comparison,
        analysis,
        assessments,
    )

    assert readiness.status == "INSUFFICIENT_EVIDENCE"


def test_unresolved_conflict_forces_conflicted_status():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    ) = make_decision()

    comparison = make_complete_comparison(
        decision,
        qdrant,
        milvus,
        qdrant_score=9.0,
        milvus_score=7.0,
    )

    analysis = make_strong_analysis(
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    )

    analysis.conflicts.append(
        EvidenceConflict(
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            supporting_signal_ids=["sig_pos"],
            opposing_signal_ids=["sig_neg"],
            conflict_score=0.9,
            resolution_status="unresolved",
        )
    )

    assessments = [
        make_assessment(
            decision.decision_id,
            "evi_1",
        )
    ]

    readiness = calculate_readiness(
        decision,
        comparison,
        analysis,
        assessments,
    )

    assert readiness.status == "CONFLICTED"

    assert (
        "important evidence conflicts remain unresolved"
        in readiness.blocking_reasons
    )


def test_critical_criterion_low_coverage_blocks_ready():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    ) = make_decision()

    comparison = make_complete_comparison(
        decision,
        qdrant,
        milvus,
        qdrant_score=10.0,
        milvus_score=0.0,
    )

    analysis = make_strong_analysis(
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    )

    for coverage in analysis.coverages:
        if (
            coverage.criterion_id
            == reliability.criterion_id
        ):
            coverage.coverage_score = 0.2

    assessments = [
        make_assessment(
            decision.decision_id,
            "evi_1",
        )
    ]

    readiness = calculate_readiness(
        decision,
        comparison,
        analysis,
        assessments,
    )

    assert readiness.status == "INSUFFICIENT_EVIDENCE"

    assert any(
        "critical criterion" in reason
        and "coverage" in reason
        for reason in readiness.blocking_reasons
    )


def test_incomplete_comparison_blocks_decision():
    (
        decision,
        qdrant,
        _,
        reliability,
        _,
    ) = make_decision()

    comparison = DecisionComparison(
        decision_id=decision.decision_id,
        status="incomplete",
        unresolved_candidate_ids=[
            qdrant.candidate_id
        ],
    )

    analysis = ResearchAnalysis(
        decision_id=decision.decision_id,
        coverages=[
            CriterionCoverage(
                candidate_id=qdrant.candidate_id,
                criterion_id=reliability.criterion_id,
                signal_count=2,
                effective_signal_count=2,
                coverage_score=1.0,
                confidence_score=1.0,
            )
        ],
    )

    readiness = calculate_readiness(
        decision,
        comparison,
        analysis,
        [],
    )

    assert readiness.status == "INSUFFICIENT_EVIDENCE"

    assert (
        "candidate eligibility remains unresolved"
        in readiness.blocking_reasons
    )


def test_research_gap_ids_are_preserved():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    ) = make_decision()

    comparison = make_complete_comparison(
        decision,
        qdrant,
        milvus,
    )

    analysis = make_strong_analysis(
        decision,
        qdrant,
        milvus,
        reliability,
        performance,
    )

    from models import ResearchGap

    analysis.research_gaps = [
        ResearchGap(
            gap_id="gap_test",
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            gap_type="low_coverage",
            severity=0.5,
            description="Need more evidence",
        )
    ]

    readiness = calculate_readiness(
        decision,
        comparison,
        analysis,
        [
            make_assessment(
                decision.decision_id,
                "evi_1",
            )
        ],
    )

    assert readiness.research_gap_ids == [
        "gap_test"
    ]
