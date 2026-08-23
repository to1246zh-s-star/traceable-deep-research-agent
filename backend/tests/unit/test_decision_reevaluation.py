from models import (
    Candidate,
    DecisionAssumption,
    DecisionCase,
    DecisionCounterfactual,
    DecisionCriterion,
    DecisionScenario,
)
from services.decision_reevaluation import (
    derive_reevaluation_triggers,
)


def decision():
    return DecisionCase(
        decision_id="dec_trigger",
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
        decision_id="dec_trigger",
        text="Deployment remains Docker-only.",
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
        decision_id="dec_trigger",
        text="Scalability weight remains 0.4.",
        assumption_type="PRIORITY",
        source_type="decision_criterion",
        source_field="weight",
        source_value="0.4",
        affected_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
        affected_criterion_ids=[
            "crit_scale",
        ],
        change_sensitivity=sensitivity,
        decision_impact=impact,
    )


def counterfactual(
    *,
    assumption_id="asm_context",
    instability="MEDIUM",
    reevaluation=True,
):
    return DecisionCounterfactual(
        counterfactual_id="cf_context",
        decision_id="dec_trigger",
        assumption_id=assumption_id,
        statement="If assumption changes.",
        assumption_type="CONTEXT",
        source_field="deployment_environment",
        recommendation_instability=instability,
        reevaluation_required=reevaluation,
    )


def scenario():
    return DecisionScenario(
        scenario_id="scn_arch",
        decision_id="dec_trigger",
        scenario_type="ARCHITECTURE",
        title="Architecture changes",
        counterfactual_ids=[
            "cf_context",
        ],
        assumption_ids=[
            "asm_context",
        ],
        scenario_instability="MEDIUM",
        reevaluation_required=True,
    )


def test_context_assumption_creates_context_trigger():
    result = derive_reevaluation_triggers(
        decision(),
        [context_assumption()],
        [],
        [],
    )

    assert len(result) == 1

    assert (
        result[0].trigger_type
        == "TECHNICAL_CONTEXT_CHANGE"
    )


def test_priority_assumption_creates_priority_trigger():
    result = derive_reevaluation_triggers(
        decision(),
        [priority_assumption()],
        [],
        [],
    )[0]

    assert (
        result.trigger_type
        == "CRITERION_PRIORITY_CHANGE"
    )


def test_deployment_change_invalidates_integration():
    result = derive_reevaluation_triggers(
        decision(),
        [context_assumption()],
        [],
        [],
    )[0]

    assert (
        "integration_assessment"
        in result.invalidated_modules
    )


def test_priority_change_invalidates_comparison_and_sensitivity():
    result = derive_reevaluation_triggers(
        decision(),
        [priority_assumption()],
        [],
        [],
    )[0]

    assert (
        "decision_comparison"
        in result.invalidated_modules
    )

    assert (
        "decision_sensitivity"
        in result.invalidated_modules
    )

    assert (
        "recommendation_robustness"
        in result.invalidated_modules
    )


def test_high_assumption_requires_reevaluation():
    result = derive_reevaluation_triggers(
        decision(),
        [priority_assumption()],
        [],
        [],
    )[0]

    assert result.trigger_impact == "HIGH"
    assert result.reevaluation_required is True


def test_unknown_is_not_false():
    result = derive_reevaluation_triggers(
        decision(),
        [
            context_assumption(
                impact="UNKNOWN",
                sensitivity="UNKNOWN",
            )
        ],
        [],
        [],
    )[0]

    assert result.trigger_impact == "UNKNOWN"
    assert result.reevaluation_required is None


def test_low_stable_trigger_can_be_false():
    result = derive_reevaluation_triggers(
        decision(),
        [
            context_assumption(
                impact="LOW",
                sensitivity="LOW",
            )
        ],
        [],
        [],
    )[0]

    assert result.trigger_impact == "LOW"
    assert result.reevaluation_required is False


def test_counterfactual_can_raise_trigger_impact():
    result = derive_reevaluation_triggers(
        decision(),
        [
            context_assumption(
                impact="LOW",
                sensitivity="LOW",
            )
        ],
        [
            counterfactual(
                instability="HIGH",
                reevaluation=True,
            )
        ],
        [],
    )[0]

    assert result.trigger_impact == "HIGH"
    assert result.reevaluation_required is True


def test_related_scenario_ids_are_attached():
    result = derive_reevaluation_triggers(
        decision(),
        [context_assumption()],
        [counterfactual()],
        [scenario()],
    )[0]

    assert result.affected_scenario_ids == [
        "scn_arch"
    ]


def test_unknown_candidate_ids_are_filtered():
    item = context_assumption()

    item.affected_candidate_ids = [
        "cand_a",
        "not_real",
    ]

    result = derive_reevaluation_triggers(
        decision(),
        [item],
        [],
        [],
    )[0]

    assert result.affected_candidate_ids == [
        "cand_a"
    ]


def test_unknown_criterion_ids_are_filtered():
    item = priority_assumption()

    item.affected_criterion_ids = [
        "crit_scale",
        "not_real",
    ]

    result = derive_reevaluation_triggers(
        decision(),
        [item],
        [],
        [],
    )[0]

    assert result.affected_criterion_ids == [
        "crit_scale"
    ]


def test_trigger_id_is_deterministic():
    item = context_assumption()

    first = derive_reevaluation_triggers(
        decision(),
        [item],
        [],
        [],
    )[0]

    second = derive_reevaluation_triggers(
        decision(),
        [item],
        [],
        [],
    )[0]

    assert first.trigger_id == second.trigger_id


def test_other_decision_assumptions_are_ignored():
    item = context_assumption()
    item.decision_id = "other_decision"

    result = derive_reevaluation_triggers(
        decision(),
        [item],
        [],
        [],
    )

    assert result == []


def test_no_scores_or_new_winner_are_synthesized():
    result = derive_reevaluation_triggers(
        decision(),
        [priority_assumption()],
        [],
        [],
    )[0]

    assert not hasattr(
        result,
        "candidate_scores",
    )

    assert not hasattr(
        result,
        "predicted_winner_id",
    )
