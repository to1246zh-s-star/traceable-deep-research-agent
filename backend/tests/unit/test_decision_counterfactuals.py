from models import (
    Candidate,
    DecisionAssumption,
    DecisionCase,
    DecisionCriterion,
    RecommendationRobustness,
)
from services.decision_counterfactuals import (
    analyze_decision_counterfactuals,
)


def decision():
    return DecisionCase(
        decision_id="dec_cf",
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


def context_assumption(
    *,
    impact="MEDIUM",
    sensitivity="MEDIUM",
    field="deployment_environment",
):
    return DecisionAssumption(
        assumption_id="asm_context",
        decision_id="dec_cf",
        text=(
            "Deployment environment remains "
            "consistent with: Docker-only."
        ),
        assumption_type="CONTEXT",
        source_type="technical_context",
        source_field=field,
        source_value="Docker-only",
        affected_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
        change_sensitivity=sensitivity,
        decision_impact=impact,
    )


def priority_assumption(
    *,
    impact="HIGH",
    sensitivity="HIGH",
):
    return DecisionAssumption(
        assumption_id="asm_priority",
        decision_id="dec_cf",
        text=(
            "The relative importance of Scalability "
            "remains at its current weight (0.4)."
        ),
        assumption_type="PRIORITY",
        source_type="decision_criterion",
        source_field="weight",
        source_value="0.4",
        affected_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
        affected_criterion_ids=[
            "crit_scale"
        ],
        change_sensitivity=sensitivity,
        decision_impact=impact,
    )


def test_context_assumption_produces_counterfactual():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            context_assumption()
        ],
        None,
    )

    assert len(result) == 1

    item = result[0]

    assert item.assumption_id == "asm_context"

    assert (
        "If this assumption no longer holds"
        in item.statement
    )


def test_deployment_change_affects_architecture_dimensions():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            context_assumption()
        ],
        None,
    )[0]

    assert "architecture_fit" in (
        result.affected_dimensions
    )

    assert "infrastructure" in (
        result.affected_dimensions
    )

    assert "integration" in (
        result.affected_dimensions
    )

    assert "operations" in (
        result.affected_dimensions
    )


def test_priority_change_affects_ranking():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            priority_assumption()
        ],
        None,
    )[0]

    assert (
        "candidate_ranking"
        in result.affected_dimensions
    )

    assert (
        "recommendation_sensitivity"
        in result.affected_dimensions
    )

    assert result.affected_criterion_ids == [
        "crit_scale"
    ]


def test_high_impact_assumption_requires_reevaluation():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            priority_assumption()
        ],
        None,
    )[0]

    assert result.recommendation_instability == (
        "HIGH"
    )

    assert result.reevaluation_required is True


def test_low_stable_assumption_does_not_require_reevaluation():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            context_assumption(
                impact="LOW",
                sensitivity="LOW",
            )
        ],
        None,
    )[0]

    assert result.recommendation_instability == (
        "LOW"
    )

    assert result.reevaluation_required is False


def test_unknown_is_not_equivalent_to_false():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            context_assumption(
                impact="UNKNOWN",
                sensitivity="UNKNOWN",
            )
        ],
        None,
    )[0]

    assert result.recommendation_instability == (
        "UNKNOWN"
    )

    assert result.reevaluation_required is None


def test_fragile_recommendation_raises_instability():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            context_assumption(
                impact="MEDIUM",
                sensitivity="MEDIUM",
            )
        ],
        RecommendationRobustness(
            decision_id="dec_cf",
            baseline_winner_id="cand_a",
            status="FRAGILE",
        ),
    )[0]

    assert result.recommendation_instability == (
        "HIGH"
    )

    assert result.reevaluation_required is True


def test_moderate_robustness_raises_low_to_medium():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            context_assumption(
                impact="LOW",
                sensitivity="LOW",
            )
        ],
        RecommendationRobustness(
            decision_id="dec_cf",
            baseline_winner_id="cand_a",
            status="MODERATE",
        ),
    )[0]

    assert result.recommendation_instability == (
        "MEDIUM"
    )

    assert result.reevaluation_required is True


def test_unknown_candidate_ids_are_dropped():
    assumption = context_assumption()

    assumption.affected_candidate_ids = [
        "cand_a",
        "not_real",
    ]

    result = analyze_decision_counterfactuals(
        decision(),
        [assumption],
        None,
    )[0]

    assert result.affected_candidate_ids == [
        "cand_a"
    ]


def test_unknown_criterion_ids_are_dropped():
    assumption = priority_assumption()

    assumption.affected_criterion_ids = [
        "crit_scale",
        "not_real",
    ]

    result = analyze_decision_counterfactuals(
        decision(),
        [assumption],
        None,
    )[0]

    assert result.affected_criterion_ids == [
        "crit_scale"
    ]


def test_other_decision_assumptions_are_ignored():
    assumption = context_assumption()
    assumption.decision_id = "other_decision"

    result = analyze_decision_counterfactuals(
        decision(),
        [assumption],
        None,
    )

    assert result == []


def test_counterfactuals_sorted_by_instability():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            context_assumption(
                impact="LOW",
                sensitivity="LOW",
            ),
            priority_assumption(
                impact="HIGH",
                sensitivity="HIGH",
            ),
        ],
        None,
    )

    assert result[0].recommendation_instability == (
        "HIGH"
    )


def test_no_candidate_scores_are_synthesized():
    result = analyze_decision_counterfactuals(
        decision(),
        [
            priority_assumption()
        ],
        None,
    )[0]

    assert not hasattr(
        result,
        "candidate_scores",
    )

    assert not hasattr(
        result,
        "predicted_winner_id",
    )
