from models import (
    Candidate,
    CandidateWeightedScore,
    DecisionCase,
    DecisionComparison,
    DecisionCriterion,
    DecisionEvaluation,
    IntegrationAssessment,
    RecommendationRobustness,
    ResearchAnalysis,
    ResearchGap,
    SensitivityResult,
    TechnicalContext,
)
from services.expected_decision_impact import (
    decompose_expected_decision_impact,
)


def make_decision():
    return DecisionCase(
        decision_id="dec_impact",
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
                criterion_id="crit_ops",
                name="Operations",
                weight=0.6,
            ),
            DecisionCriterion(
                criterion_id="crit_scale",
                name="Scalability",
                weight=0.4,
            ),
        ],
    )


def comparison():
    return DecisionComparison(
        decision_id="dec_impact",
        status="complete",
        candidate_scores=[
            CandidateWeightedScore(
                candidate_id="cand_a",
                weighted_score=8.0,
                rank=1,
            ),
            CandidateWeightedScore(
                candidate_id="cand_b",
                weighted_score=7.5,
                rank=2,
            ),
        ],
        ranked_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
    )


def evaluation():
    return DecisionEvaluation(
        decision_id="dec_impact",
        status="complete",
        eligible_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
    )


def gap(
    candidate="cand_a",
    criterion="crit_ops",
    gap_type="low_coverage",
    impact="MEDIUM",
):
    return ResearchGap(
        gap_id="gap_test",
        candidate_id=candidate,
        criterion_id=criterion,
        gap_type=gap_type,
        severity=0.7,
        description="Need evidence",
        decision_impact=impact,
        priority=2,
    )


def run(
    item,
    *,
    comp=None,
    eval_result=None,
    sensitivity=None,
    robustness=None,
    context=None,
    assessments=None,
):
    analysis = ResearchAnalysis(
        decision_id="dec_impact",
        research_gaps=[item],
        status="gaps_detected",
    )

    return decompose_expected_decision_impact(
        make_decision(),
        analysis,
        comp or comparison(),
        eval_result or evaluation(),
        sensitivity or [],
        robustness,
        context,
        assessments or [],
    ).research_gaps[0].expected_decision_impact


def test_near_flip_has_high_ranking_impact():
    result = run(
        gap(
            candidate="cand_b",
            criterion="crit_scale",
            impact="HIGH",
        ),
        sensitivity=[
            SensitivityResult(
                decision_id="dec_impact",
                criterion_id="crit_scale",
                baseline_weight=0.4,
                baseline_winner_id="cand_a",
                score_margin_before=0.5,
                recommendation_changes=True,
                weight_delta=0.08,
                competing_candidate_id="cand_b",
            )
        ],
    )

    assert result is not None
    assert result.ranking_impact == "HIGH"
    assert result.overall_impact == "HIGH"


def test_unresolved_candidate_has_high_constraint_impact():
    item = evaluation()
    item.status = "incomplete"
    item.eligible_candidate_ids = [
        "cand_a"
    ]
    item.unresolved_candidate_ids = [
        "cand_b"
    ]

    result = run(
        gap(
            candidate="cand_b",
            impact="HIGH",
        ),
        eval_result=item,
    )

    assert result.constraint_impact == "HIGH"
    assert result.overall_impact == "HIGH"


def test_unknown_architecture_without_context():
    result = run(
        gap(),
    )

    assert result.architecture_impact == "UNKNOWN"


def test_incomplete_architecture_is_medium():
    result = run(
        gap(
            candidate="cand_b"
        ),
        context=TechnicalContext(
            existing_stack=["Python"]
        ),
        assessments=[
            IntegrationAssessment(
                decision_id="dec_impact",
                candidate_id="cand_b",
                integration_complexity="UNKNOWN",
                migration_complexity="LOW",
                operational_change="LOW",
                infrastructure_change="LOW",
            )
        ],
    )

    assert result.architecture_impact == "MEDIUM"


def test_complete_architecture_is_low():
    result = run(
        gap(),
        context=TechnicalContext(
            existing_stack=["Python"]
        ),
        assessments=[
            IntegrationAssessment(
                decision_id="dec_impact",
                candidate_id="cand_a",
                integration_complexity="LOW",
                migration_complexity="LOW",
                operational_change="LOW",
                infrastructure_change="LOW",
            )
        ],
    )

    assert result.architecture_impact == "LOW"


def test_decision_relevant_conflict_is_high():
    result = run(
        gap(
            candidate="cand_a",
            gap_type="conflicting_evidence",
            impact="HIGH",
        )
    )

    assert (
        result.conflict_resolution_impact
        == "HIGH"
    )


def test_fragile_recommendation_has_high_robustness_impact():
    result = run(
        gap(
            candidate="cand_a",
            impact="HIGH",
        ),
        robustness=RecommendationRobustness(
            decision_id="dec_impact",
            baseline_winner_id="cand_a",
            status="FRAGILE",
        ),
    )

    assert result.robustness_impact == "HIGH"


def test_robust_recommendation_has_low_robustness_impact():
    result = run(
        gap(),
        robustness=RecommendationRobustness(
            decision_id="dec_impact",
            baseline_winner_id="cand_a",
            status="ROBUST",
        ),
    )

    assert result.robustness_impact == "LOW"


def test_incomplete_comparison_makes_overall_unknown():
    result = run(
        gap(),
        comp=DecisionComparison(
            decision_id="dec_impact",
            status="incomplete",
        ),
    )

    assert result.overall_impact == "UNKNOWN"
    assert result.ranking_impact == "UNKNOWN"


def test_phase18_never_downgrades_phase17_impact():
    result = run(
        gap(
            candidate="cand_b",
            criterion="crit_ops",
            impact="HIGH",
        )
    )

    assert result.overall_impact == "HIGH"


def test_decomposition_does_not_change_gap_priority():
    item = gap(
        candidate="cand_a",
        impact="MEDIUM",
    )

    original_priority = item.priority

    analysis = ResearchAnalysis(
        decision_id="dec_impact",
        research_gaps=[item],
    )

    decompose_expected_decision_impact(
        make_decision(),
        analysis,
        comparison(),
        evaluation(),
        [],
        None,
        None,
        [],
    )

    assert item.priority == original_priority
