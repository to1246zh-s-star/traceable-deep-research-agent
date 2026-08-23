from models import (
    Candidate,
    CandidateDecisionResult,
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
from services.decision_impact_gaps import (
    enrich_research_gaps_with_decision_impact,
)


def make_decision():
    return DecisionCase(
        decision_id="dec_gap_impact",
        question="Choose A or B",
        candidates=[
            Candidate(candidate_id="cand_a", name="A"),
            Candidate(candidate_id="cand_b", name="B"),
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


def make_comparison():
    return DecisionComparison(
        decision_id="dec_gap_impact",
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
        ranked_candidate_ids=["cand_a", "cand_b"],
    )


def make_evaluation():
    return DecisionEvaluation(
        decision_id="dec_gap_impact",
        status="complete",
        eligible_candidate_ids=["cand_a", "cand_b"],
    )


def gap(
    gap_id,
    candidate_id,
    criterion_id,
    *,
    severity=0.5,
    gap_type="low_coverage",
    query=None,
):
    return ResearchGap(
        gap_id=gap_id,
        candidate_id=candidate_id,
        criterion_id=criterion_id,
        gap_type=gap_type,
        severity=severity,
        description="Need more evidence",
        suggested_query=(
            query
            or f"{candidate_id} {criterion_id} evidence"
        ),
    )


def enrich(
    gaps,
    *,
    comparison=None,
    evaluation=None,
    sensitivity=None,
    context=None,
    assessments=None,
    robustness=None,
):
    analysis = ResearchAnalysis(
        decision_id="dec_gap_impact",
        research_gaps=gaps,
        status="gaps_detected",
    )

    return enrich_research_gaps_with_decision_impact(
        make_decision(),
        analysis,
        comparison or make_comparison(),
        evaluation or make_evaluation(),
        sensitivity or [],
        robustness,
        context,
        assessments or [],
    )


def test_near_flip_criterion_is_high_impact():
    analysis = enrich(
        [
            gap(
                "gap_scale",
                "cand_b",
                "crit_scale",
            )
        ],
        sensitivity=[
            SensitivityResult(
                decision_id="dec_gap_impact",
                criterion_id="crit_scale",
                baseline_weight=0.4,
                baseline_winner_id="cand_a",
                score_margin_before=0.5,
                recommendation_changes=True,
                switch_threshold=0.48,
                weight_delta=0.08,
                direction_of_change="increase",
                competing_candidate_id="cand_b",
                score_margin_after=-0.1,
            )
        ],
    )

    result = analysis.research_gaps[0]

    assert result.decision_impact == "HIGH"
    assert result.priority == 3
    assert result.impact_reasons


def test_unresolved_candidate_is_high_impact():
    evaluation = make_evaluation()
    evaluation.status = "incomplete"
    evaluation.eligible_candidate_ids = ["cand_a"]
    evaluation.unresolved_candidate_ids = ["cand_b"]
    evaluation.candidate_results = [
        CandidateDecisionResult(
            candidate_id="cand_a",
            status="eligible",
        ),
        CandidateDecisionResult(
            candidate_id="cand_b",
            status="unresolved",
            missing_constraint_ids=[
                "con_self_hosted"
            ],
        ),
    ]

    analysis = enrich(
        [
            gap(
                "gap_b",
                "cand_b",
                "crit_ops",
            )
        ],
        evaluation=evaluation,
    )

    result = analysis.research_gaps[0]

    assert result.decision_impact == "HIGH"
    assert any(
        "hard constraints" in reason
        for reason in result.impact_reasons
    )


def test_winner_gap_is_medium():
    analysis = enrich(
        [
            gap(
                "gap_winner",
                "cand_a",
                "crit_ops",
            )
        ]
    )

    result = analysis.research_gaps[0]

    assert result.decision_impact == "MEDIUM"
    assert result.priority == 2


def test_unrelated_gap_is_low():
    analysis = enrich(
        [
            gap(
                "gap_other",
                "cand_b",
                "crit_ops",
            )
        ]
    )

    result = analysis.research_gaps[0]

    assert result.decision_impact == "LOW"
    assert result.priority == 1


def test_incomplete_comparison_is_unknown():
    comparison = DecisionComparison(
        decision_id="dec_gap_impact",
        status="incomplete",
    )

    analysis = enrich(
        [
            gap(
                "gap_unknown",
                "cand_a",
                "crit_ops",
            )
        ],
        comparison=comparison,
    )

    result = analysis.research_gaps[0]

    assert result.decision_impact == "UNKNOWN"
    assert result.priority == 0


def test_context_is_added_to_query():
    context = TechnicalContext(
        deployment_environment=["Docker-only"],
        existing_stack=["Python", "FastAPI"],
        team_capabilities=["small DevOps team"],
    )

    analysis = enrich(
        [
            gap(
                "gap_context",
                "cand_a",
                "crit_ops",
                query="A operations benchmark",
            )
        ],
        context=context,
    )

    result = analysis.research_gaps[0]

    assert "Docker-only" in result.suggested_query
    assert "Python" in result.suggested_query
    assert "FastAPI" in result.suggested_query
    assert "small DevOps team" in result.suggested_query

    assert (
        "deployment_environment"
        in result.context_dimensions
    )


def test_context_query_does_not_duplicate_existing_term():
    context = TechnicalContext(
        deployment_environment=["Docker-only"]
    )

    analysis = enrich(
        [
            gap(
                "gap_context",
                "cand_a",
                "crit_ops",
                query="A operations Docker-only benchmark",
            )
        ],
        context=context,
    )

    query = analysis.research_gaps[0].suggested_query

    assert query.lower().count("docker-only") == 1


def test_missing_context_does_not_change_query():
    original = "A operations benchmark"

    analysis = enrich(
        [
            gap(
                "gap_context",
                "cand_a",
                "crit_ops",
                query=original,
            )
        ]
    )

    result = analysis.research_gaps[0]

    assert result.suggested_query == original
    assert result.context_dimensions == []


def test_architecture_unknown_is_medium():
    context = TechnicalContext(
        existing_stack=["Python"]
    )

    assessments = [
        IntegrationAssessment(
            decision_id="dec_gap_impact",
            candidate_id="cand_a",
            integration_complexity="LOW",
            migration_complexity="LOW",
            operational_change="LOW",
            infrastructure_change="LOW",
        ),
        IntegrationAssessment(
            decision_id="dec_gap_impact",
            candidate_id="cand_b",
            integration_complexity="UNKNOWN",
            migration_complexity="LOW",
            operational_change="LOW",
            infrastructure_change="LOW",
        ),
    ]

    analysis = enrich(
        [
            gap(
                "gap_arch",
                "cand_b",
                "crit_ops",
            )
        ],
        context=context,
        assessments=assessments,
    )

    result = analysis.research_gaps[0]

    assert result.decision_impact == "MEDIUM"
    assert any(
        "Architecture fit" in reason
        for reason in result.impact_reasons
    )


def test_impact_order_beats_raw_severity():
    analysis = enrich(
        [
            gap(
                "gap_low",
                "cand_b",
                "crit_ops",
                severity=0.99,
            ),
            gap(
                "gap_winner",
                "cand_a",
                "crit_ops",
                severity=0.20,
            ),
        ]
    )

    assert [
        item.gap_id
        for item in analysis.research_gaps
    ] == [
        "gap_winner",
        "gap_low",
    ]


def test_fragile_winner_gap_is_medium():
    robustness = RecommendationRobustness(
        decision_id="dec_gap_impact",
        baseline_winner_id="cand_a",
        status="FRAGILE",
    )

    analysis = enrich(
        [
            gap(
                "gap_fragile",
                "cand_a",
                "crit_ops",
            )
        ],
        robustness=robustness,
    )

    result = analysis.research_gaps[0]

    assert result.decision_impact == "MEDIUM"
    assert any(
        "fragile" in reason.lower()
        for reason in result.impact_reasons
    )
