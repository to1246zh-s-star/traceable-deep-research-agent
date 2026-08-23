from models import (
    Candidate,
    DecisionCase,
    DecisionCounterfactual,
    DecisionCriterion,
)
from services.decision_scenarios import (
    analyze_decision_scenarios,
)


def decision():
    return DecisionCase(
        decision_id="dec_scenario",
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


def counterfactual(
    counterfactual_id,
    *,
    assumption_id,
    assumption_type="CONTEXT",
    field="deployment_environment",
    instability="MEDIUM",
    reevaluation=True,
    candidates=None,
    criteria=None,
    dimensions=None,
):
    return DecisionCounterfactual(
        counterfactual_id=counterfactual_id,
        decision_id="dec_scenario",
        assumption_id=assumption_id,
        statement="If assumption changes.",
        assumption_type=assumption_type,
        source_field=field,
        affected_candidate_ids=(
            candidates
            if candidates is not None
            else ["cand_a", "cand_b"]
        ),
        affected_criterion_ids=(
            criteria
            if criteria is not None
            else []
        ),
        affected_dimensions=(
            dimensions
            if dimensions is not None
            else ["architecture_fit"]
        ),
        recommendation_instability=instability,
        reevaluation_required=reevaluation,
    )


def test_architecture_counterfactual_creates_architecture_scenario():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_1",
                assumption_id="asm_1",
                field="deployment_environment",
            )
        ],
    )

    assert len(result) == 1
    assert result[0].scenario_type == "ARCHITECTURE"


def test_priority_counterfactual_creates_priority_scenario():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_priority",
                assumption_id="asm_priority",
                assumption_type="PRIORITY",
                field="weight",
                criteria=["crit_scale"],
                dimensions=[
                    "criterion_priority",
                    "candidate_ranking",
                ],
            )
        ],
    )

    assert result[0].scenario_type == "PRIORITY"
    assert result[0].affected_criterion_ids == [
        "crit_scale"
    ]


def test_multiple_architecture_changes_are_grouped():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_1",
                assumption_id="asm_1",
                field="deployment_environment",
            ),
            counterfactual(
                "cf_2",
                assumption_id="asm_2",
                field="existing_stack",
            ),
        ],
    )

    assert len(result) == 1

    scenario = result[0]

    assert scenario.scenario_type == "ARCHITECTURE"

    assert set(
        scenario.counterfactual_ids
    ) == {
        "cf_1",
        "cf_2",
    }


def test_different_domains_create_separate_scenarios():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_arch",
                assumption_id="asm_arch",
                field="deployment_environment",
            ),
            counterfactual(
                "cf_budget",
                assumption_id="asm_budget",
                field="budget_constraints",
            ),
        ],
    )

    assert {
        item.scenario_type
        for item in result
    } == {
        "ARCHITECTURE",
        "ECONOMICS",
    }


def test_scenario_instability_uses_max_known_impact():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_low",
                assumption_id="asm_low",
                field="deployment_environment",
                instability="LOW",
                reevaluation=False,
            ),
            counterfactual(
                "cf_high",
                assumption_id="asm_high",
                field="existing_stack",
                instability="HIGH",
                reevaluation=True,
            ),
        ],
    )[0]

    assert result.scenario_instability == "HIGH"


def test_two_mediums_do_not_invent_high_instability():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_1",
                assumption_id="asm_1",
                instability="MEDIUM",
            ),
            counterfactual(
                "cf_2",
                assumption_id="asm_2",
                field="existing_stack",
                instability="MEDIUM",
            ),
        ],
    )[0]

    assert result.scenario_instability == "MEDIUM"


def test_any_true_requires_reevaluation():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_false",
                assumption_id="asm_false",
                instability="LOW",
                reevaluation=False,
            ),
            counterfactual(
                "cf_true",
                assumption_id="asm_true",
                field="existing_stack",
                instability="MEDIUM",
                reevaluation=True,
            ),
        ],
    )[0]

    assert result.reevaluation_required is True


def test_unknown_reevaluation_is_not_false():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_unknown",
                assumption_id="asm_unknown",
                instability="UNKNOWN",
                reevaluation=None,
            )
        ],
    )[0]

    assert result.scenario_instability == "UNKNOWN"
    assert result.reevaluation_required is None


def test_all_low_false_can_remain_false():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_low",
                assumption_id="asm_low",
                instability="LOW",
                reevaluation=False,
            )
        ],
    )[0]

    assert result.scenario_instability == "LOW"
    assert result.reevaluation_required is False


def test_affected_dimensions_are_deduplicated():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_1",
                assumption_id="asm_1",
                dimensions=[
                    "architecture_fit",
                    "integration",
                ],
            ),
            counterfactual(
                "cf_2",
                assumption_id="asm_2",
                field="existing_stack",
                dimensions=[
                    "architecture_fit",
                    "migration",
                ],
            ),
        ],
    )[0]

    assert result.affected_dimensions == [
        "architecture_fit",
        "integration",
        "migration",
    ]


def test_unknown_candidate_ids_are_dropped():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_1",
                assumption_id="asm_1",
                candidates=[
                    "cand_a",
                    "not_real",
                ],
            )
        ],
    )[0]

    assert result.affected_candidate_ids == [
        "cand_a"
    ]


def test_other_decision_counterfactuals_are_ignored():
    item = counterfactual(
        "cf_other",
        assumption_id="asm_other",
    )

    item.decision_id = "another_decision"

    result = analyze_decision_scenarios(
        decision(),
        [item],
    )

    assert result == []


def test_scenario_id_is_deterministic():
    inputs = [
        counterfactual(
            "cf_1",
            assumption_id="asm_1",
        ),
        counterfactual(
            "cf_2",
            assumption_id="asm_2",
            field="existing_stack",
        ),
    ]

    first = analyze_decision_scenarios(
        decision(),
        inputs,
    )[0]

    second = analyze_decision_scenarios(
        decision(),
        list(reversed(inputs)),
    )[0]

    assert first.scenario_id == second.scenario_id


def test_no_candidate_scores_or_predicted_winner():
    result = analyze_decision_scenarios(
        decision(),
        [
            counterfactual(
                "cf_1",
                assumption_id="asm_1",
            )
        ],
    )[0]

    assert not hasattr(
        result,
        "candidate_scores",
    )

    assert not hasattr(
        result,
        "predicted_winner_id",
    )
