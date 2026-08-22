from models import (
    Candidate,
    CandidateWeightedScore,
    DecisionCase,
    DecisionComparison,
    DecisionEvaluation,
    DecisionReadiness,
    DecisionCriterion,
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceQuality,
    EvidenceSignal,
    IntegrationAssessment,
    SensitivityResult,
    SourceQuality,
)
from services.recommendation_robustness import (
    analyze_recommendation_robustness,
)


def make_decision():
    return DecisionCase(
        decision_id="dec_robust",
        question="Choose A or B",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            ),
            Candidate(
                candidate_id="cand_b",
                name="B",
            ),
        ],
        criteria=[
            DecisionCriterion(
                criterion_id="crit_perf",
                name="Performance",
                weight=0.6,
            ),
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operations",
                weight=0.4,
            ),
        ],
    )


def make_comparison():
    return DecisionComparison(
        decision_id="dec_robust",
        status="complete",
        candidate_scores=[
            CandidateWeightedScore(
                candidate_id="cand_a",
                weighted_score=8.0,
                rank=1,
            ),
            CandidateWeightedScore(
                candidate_id="cand_b",
                weighted_score=7.0,
                rank=2,
            ),
        ],
        ranked_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
    )


def make_evaluation():
    return DecisionEvaluation(
        decision_id="dec_robust",
        status="complete",
        eligible_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
    )


def make_readiness(
    *,
    overall=0.9,
    agreement=0.9,
    margin=0.3,
):
    return DecisionReadiness(
        decision_id="dec_robust",
        overall_score=overall,
        status="READY",
        criterion_coverage=0.9,
        evidence_quality=0.9,
        applicability=0.9,
        agreement_score=agreement,
        decision_margin=margin,
    )


def make_architecture():
    return [
        IntegrationAssessment(
            decision_id="dec_robust",
            candidate_id="cand_a",
            integration_complexity="LOW",
            migration_complexity="LOW",
            operational_change="LOW",
            infrastructure_change="LOW",
        ),
        IntegrationAssessment(
            decision_id="dec_robust",
            candidate_id="cand_b",
            integration_complexity="MEDIUM",
            migration_complexity="MEDIUM",
            operational_change="MEDIUM",
            infrastructure_change="MEDIUM",
        ),
    ]


def analyze(
    *,
    comparison=None,
    evaluation=None,
    sensitivity=None,
    readiness=None,
    evidence_assessments=None,
    evidence_signals=None,
    integration_assessments=None,
):
    return analyze_recommendation_robustness(
        make_decision(),
        comparison or make_comparison(),
        evaluation or make_evaluation(),
        sensitivity or [],
        readiness or make_readiness(),
        evidence_assessments or [],
        evidence_signals or [],
        (
            make_architecture()
            if integration_assessments is None
            else integration_assessments
        ),
    )


def test_complete_stable_decision_is_robust():
    result = analyze(
        sensitivity=[
            SensitivityResult(
                decision_id="dec_robust",
                criterion_id="crit_perf",
                baseline_weight=0.6,
                baseline_winner_id="cand_a",
                score_margin_before=1.0,
                recommendation_changes=False,
            ),
            SensitivityResult(
                decision_id="dec_robust",
                criterion_id="crit_ops",
                baseline_weight=0.4,
                baseline_winner_id="cand_a",
                score_margin_before=1.0,
                recommendation_changes=False,
            ),
        ]
    )

    assert result.status == "ROBUST"
    assert result.baseline_winner_id == "cand_a"
    assert result.score_margin == 1.0
    assert result.flip_count == 0
    assert result.tested_criteria_count == 2


def test_incomplete_comparison_is_unknown():
    comparison = DecisionComparison(
        decision_id="dec_robust",
        status="incomplete",
        unresolved_candidate_ids=[
            "cand_b"
        ],
    )

    result = analyze(
        comparison=comparison
    )

    assert result.status == "UNKNOWN"
    assert result.baseline_winner_id is None
    assert result.unresolved_candidate_ids == [
        "cand_b"
    ]


def test_near_sensitivity_flip_is_fragile():
    result = analyze(
        sensitivity=[
            SensitivityResult(
                decision_id="dec_robust",
                criterion_id="crit_perf",
                baseline_weight=0.6,
                baseline_winner_id="cand_a",
                score_margin_before=1.0,
                recommendation_changes=True,
                switch_threshold=0.68,
                weight_delta=0.08,
                direction_of_change="increase",
                competing_candidate_id="cand_b",
                score_margin_after=-0.1,
            )
        ]
    )

    assert result.status == "FRAGILE"
    assert result.flip_count == 1
    assert (
        result.minimum_relative_flip_delta
        == 0.08
    )
    assert result.unstable_criterion_ids == [
        "crit_perf"
    ]


def test_distant_flip_is_moderate():
    result = analyze(
        sensitivity=[
            SensitivityResult(
                decision_id="dec_robust",
                criterion_id="crit_perf",
                baseline_weight=0.6,
                baseline_winner_id="cand_a",
                score_margin_before=1.0,
                recommendation_changes=True,
                switch_threshold=0.8,
                weight_delta=0.2,
                direction_of_change="increase",
                competing_candidate_id="cand_b",
                score_margin_after=-0.1,
            )
        ]
    )

    assert result.status == "MODERATE"
    assert result.flip_count == 1


def test_low_readiness_is_fragile():
    result = analyze(
        readiness=make_readiness(
            overall=0.4,
        )
    )

    assert result.status == "FRAGILE"


def test_low_agreement_is_moderate():
    result = analyze(
        readiness=make_readiness(
            agreement=0.5,
        )
    )

    assert result.status == "MODERATE"


def test_narrow_decision_margin_is_moderate():
    result = analyze(
        readiness=make_readiness(
            margin=0.05,
        )
    )

    assert result.status == "MODERATE"


def test_unknown_winner_architecture_is_moderate():
    architecture = make_architecture()

    architecture[0].operational_change = (
        "UNKNOWN"
    )

    result = analyze(
        integration_assessments=architecture
    )

    assert result.status == "MODERATE"
    assert (
        "cand_a"
        in result.architecture_unknown_candidate_ids
    )


def test_missing_architecture_assessment_is_unknown_fit():
    architecture = [
        make_architecture()[1]
    ]

    result = analyze(
        integration_assessments=architecture
    )

    assert result.status == "MODERATE"
    assert (
        "cand_a"
        in result.architecture_unknown_candidate_ids
    )


def test_weak_winner_evidence_is_moderate():
    assessment = EvidenceAssessment(
        evidence_id="evi_a",
        decision_id="dec_robust",
        source_quality=SourceQuality(
            evidence_id="evi_a",
            source_type="web",
            confidence=0.3,
        ),
        evidence_quality=EvidenceQuality(
            evidence_id="evi_a",
            quality_score=0.3,
            completeness=0.3,
        ),
        applicability=EvidenceApplicability(
            evidence_id="evi_a",
            decision_id="dec_robust",
            applicability_score=0.3,
        ),
        overall_score=0.3,
    )

    signal = EvidenceSignal(
        evidence_id="evi_a",
        candidate_id="cand_a",
        criterion_id="crit_perf",
        direction="positive",
        strength=0.8,
        source_confidence=0.3,
        applicability=0.3,
    )

    result = analyze(
        evidence_assessments=[
            assessment
        ],
        evidence_signals=[
            signal
        ],
    )

    assert result.status == "MODERATE"
    assert (
        result.weak_evidence_candidate_ids
        == ["cand_a"]
    )


def test_weak_nonwinner_does_not_downgrade_winner():
    assessment = EvidenceAssessment(
        evidence_id="evi_b",
        decision_id="dec_robust",
        source_quality=SourceQuality(
            evidence_id="evi_b",
            source_type="web",
            confidence=0.2,
        ),
        evidence_quality=EvidenceQuality(
            evidence_id="evi_b",
            quality_score=0.2,
            completeness=0.2,
        ),
        applicability=EvidenceApplicability(
            evidence_id="evi_b",
            decision_id="dec_robust",
            applicability_score=0.2,
        ),
        overall_score=0.2,
    )

    signal = EvidenceSignal(
        evidence_id="evi_b",
        candidate_id="cand_b",
        criterion_id="crit_perf",
        direction="positive",
        strength=0.5,
        source_confidence=0.2,
        applicability=0.2,
    )

    result = analyze(
        evidence_assessments=[
            assessment
        ],
        evidence_signals=[
            signal
        ],
    )

    assert (
        result.weak_evidence_candidate_ids
        == ["cand_b"]
    )
    assert result.status == "ROBUST"


def test_unresolved_constraints_are_fragile():
    evaluation = make_evaluation()

    evaluation.status = "incomplete"
    evaluation.unresolved_candidate_ids = [
        "cand_b"
    ]

    # Complete comparison is intentionally supplied to ensure the
    # robustness layer remains conservative about unresolved constraints.
    result = analyze(
        evaluation=evaluation
    )

    assert result.status == "FRAGILE"
    assert result.unresolved_candidate_ids == [
        "cand_b"
    ]
