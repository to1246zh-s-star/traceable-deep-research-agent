from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    IntegrationAssessment,
    RecommendationRobustness,
    SensitivityResult,
    TechnicalContext,
)
from services.decision_assumptions import (
    analyze_decision_assumptions,
)


def decision():
    return DecisionCase(
        decision_id="dec_assumption",
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


def test_no_context_still_creates_priority_assumptions():
    result = analyze_decision_assumptions(
        decision(),
        None,
        [],
        None,
        [],
    )

    assert len(result) == 2

    assert all(
        item.assumption_type == "PRIORITY"
        for item in result
    )


def test_context_values_become_explicit_assumptions():
    result = analyze_decision_assumptions(
        decision(),
        TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ],
            team_capabilities=[
                "small DevOps team"
            ],
        ),
        [],
        None,
        [],
    )

    context_items = [
        item
        for item in result
        if item.assumption_type == "CONTEXT"
    ]

    assert len(context_items) == 2

    values = {
        item.source_value
        for item in context_items
    }

    assert values == {
        "Docker-only",
        "small DevOps team",
    }


def test_context_assumption_affects_all_candidates():
    result = analyze_decision_assumptions(
        decision(),
        TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
        [],
        None,
        [],
    )

    item = next(
        entry
        for entry in result
        if entry.assumption_type == "CONTEXT"
    )

    assert set(
        item.affected_candidate_ids
    ) == {
        "cand_a",
        "cand_b",
    }


def test_near_flip_weight_assumption_is_high_impact():
    result = analyze_decision_assumptions(
        decision(),
        None,
        [
            SensitivityResult(
                decision_id="dec_assumption",
                criterion_id="crit_scale",
                baseline_weight=0.4,
                baseline_winner_id="cand_a",
                score_margin_before=0.5,
                recommendation_changes=True,
                weight_delta=0.08,
                competing_candidate_id="cand_b",
            )
        ],
        None,
        [],
    )

    item = next(
        entry
        for entry in result
        if entry.affected_criterion_ids
        == ["crit_scale"]
    )

    assert item.decision_impact == "HIGH"
    assert item.change_sensitivity == "HIGH"


def test_far_flip_weight_assumption_is_medium():
    result = analyze_decision_assumptions(
        decision(),
        None,
        [
            SensitivityResult(
                decision_id="dec_assumption",
                criterion_id="crit_scale",
                baseline_weight=0.4,
                baseline_winner_id="cand_a",
                score_margin_before=0.5,
                recommendation_changes=True,
                weight_delta=0.20,
                competing_candidate_id="cand_b",
            )
        ],
        None,
        [],
    )

    item = next(
        entry
        for entry in result
        if entry.affected_criterion_ids
        == ["crit_scale"]
    )

    assert item.decision_impact == "MEDIUM"


def test_non_flipping_weight_assumption_is_low():
    result = analyze_decision_assumptions(
        decision(),
        None,
        [],
        None,
        [],
    )

    assert all(
        item.decision_impact == "LOW"
        for item in result
    )


def test_architecture_uncertainty_raises_context_impact():
    result = analyze_decision_assumptions(
        decision(),
        TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
        [],
        None,
        [
            IntegrationAssessment(
                decision_id="dec_assumption",
                candidate_id="cand_a",
                integration_complexity="UNKNOWN",
                migration_complexity="LOW",
                operational_change="LOW",
                infrastructure_change="LOW",
            ),
            IntegrationAssessment(
                decision_id="dec_assumption",
                candidate_id="cand_b",
                integration_complexity="LOW",
                migration_complexity="LOW",
                operational_change="LOW",
                infrastructure_change="LOW",
            ),
        ],
    )

    item = next(
        entry
        for entry in result
        if entry.assumption_type == "CONTEXT"
    )

    assert item.decision_impact == "HIGH"


def test_fragile_recommendation_raises_context_change_sensitivity():
    result = analyze_decision_assumptions(
        decision(),
        TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
        [],
        RecommendationRobustness(
            decision_id="dec_assumption",
            baseline_winner_id="cand_a",
            status="FRAGILE",
        ),
        [],
    )

    item = next(
        entry
        for entry in result
        if entry.assumption_type == "CONTEXT"
    )

    assert item.change_sensitivity == "HIGH"


def test_assumptions_are_sorted_by_decision_impact():
    result = analyze_decision_assumptions(
        decision(),
        None,
        [
            SensitivityResult(
                decision_id="dec_assumption",
                criterion_id="crit_scale",
                baseline_weight=0.4,
                baseline_winner_id="cand_a",
                score_margin_before=0.5,
                recommendation_changes=True,
                weight_delta=0.08,
                competing_candidate_id="cand_b",
            )
        ],
        None,
        [],
    )

    assert result[0].decision_impact == "HIGH"


def test_no_constraints_are_invented_as_assumptions():
    result = analyze_decision_assumptions(
        decision(),
        None,
        [],
        None,
        [],
    )

    assert all(
        item.source_type != "constraint"
        for item in result
    )
