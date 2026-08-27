import pytest

from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    DecisionReevaluationTrigger,
    ReevaluationAssessment,
)
from services.reevaluation_planner import (
    build_reevaluation_plan,
)


def decision():
    return DecisionCase(
        decision_id="dec_test",
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
                weight=1.0,
            )
        ],
    )


def trigger(
    *,
    trigger_id="trg_context",
    reevaluation_required=True,
):
    return DecisionReevaluationTrigger(
        trigger_id=trigger_id,
        decision_id="dec_test",
        trigger_type="TECHNICAL_CONTEXT_CHANGE",
        source_type="technical_context",
        source_field="deployment_environment",
        source_value="Docker-only",
        affected_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
        affected_criterion_ids=[
            "crit_ops",
        ],
        affected_scenario_ids=[
            "scn_arch",
        ],
        invalidated_modules=[
            "integration_assessment",
            "scenario_analysis",
        ],
        trigger_impact="HIGH",
        reevaluation_required=reevaluation_required,
        rationale=[
            "Deployment context changed."
        ],
    )


def assessment(
    *,
    status="REQUIRED",
):
    return ReevaluationAssessment(
        decision_id="dec_test",
        status=status,
        matched_trigger_ids=[
            "trg_context",
        ],
        invalidated_modules=[
            "scenario_analysis",
            "integration_assessment",
            "scenario_analysis",
        ],
        affected_candidate_ids=[
            "cand_b",
            "cand_a",
            "cand_a",
        ],
        affected_criterion_ids=[
            "crit_ops",
        ],
        affected_scenario_ids=[
            "scn_arch",
        ],
        reasons=[
            "Deployment context changed."
        ],
    )


def test_required_assessment_builds_plan():
    result = build_reevaluation_plan(
        decision(),
        assessment(),
        [trigger()],
    )

    assert result.status == "REQUIRED"

    assert result.modules_to_recompute == [
        "integration_assessment",
        "scenario_analysis",
    ]

    assert result.candidate_ids_to_recheck == [
        "cand_a",
        "cand_b",
    ]

    assert result.criterion_ids_to_recheck == [
        "crit_ops",
    ]

    assert result.scenario_ids_to_recheck == [
        "scn_arch",
    ]


def test_research_query_is_deterministic():
    result = build_reevaluation_plan(
        decision(),
        assessment(),
        [trigger()],
    )

    assert result.research_queries == [
        (
            "A B Operations deployment environment "
            "technical context change updated evidence"
        )
    ]


def test_plan_does_not_create_research_gaps():
    result = build_reevaluation_plan(
        decision(),
        assessment(),
        [trigger()],
    )

    assert not hasattr(
        result,
        "research_gaps",
    )

    assert not hasattr(
        result,
        "tasks",
    )


def test_plan_does_not_synthesize_decision_outputs():
    result = build_reevaluation_plan(
        decision(),
        assessment(),
        [trigger()],
    )

    assert not hasattr(
        result,
        "candidate_scores",
    )

    assert not hasattr(
        result,
        "predicted_winner_id",
    )

    assert not hasattr(
        result,
        "recommendation",
    )


def test_not_required_has_no_research_queries():
    result = build_reevaluation_plan(
        decision(),
        assessment(
            status="NOT_REQUIRED"
        ),
        [trigger()],
    )

    assert result.status == "NOT_REQUIRED"
    assert result.research_queries == []


def test_unknown_has_no_research_queries():
    result = build_reevaluation_plan(
        decision(),
        ReevaluationAssessment(
            decision_id="dec_test",
            status="UNKNOWN",
        ),
        [trigger()],
    )

    assert result.status == "UNKNOWN"
    assert result.research_queries == []


def test_recommended_can_create_research_direction():
    result = build_reevaluation_plan(
        decision(),
        assessment(
            status="RECOMMENDED"
        ),
        [
            trigger(
                reevaluation_required=False
            )
        ],
    )

    assert result.status == "RECOMMENDED"
    assert result.research_queries


def test_unknown_trigger_id_is_not_invented():
    item = assessment()
    item.matched_trigger_ids = [
        "trg_missing",
    ]

    result = build_reevaluation_plan(
        decision(),
        item,
        [trigger()],
    )

    assert result.matched_trigger_ids == [
        "trg_missing"
    ]

    assert result.research_queries == []


def test_other_decision_trigger_is_ignored():
    other = trigger()
    other.decision_id = "dec_other"

    result = build_reevaluation_plan(
        decision(),
        assessment(),
        [other],
    )

    assert result.research_queries == []


def test_decision_id_mismatch_is_rejected():
    item = assessment()
    item.decision_id = "dec_other"

    with pytest.raises(
        ValueError,
        match="assessment decision_id",
    ):
        build_reevaluation_plan(
            decision(),
            item,
            [trigger()],
        )


def test_input_assessment_is_not_mutated():
    item = assessment()

    before = list(
        item.invalidated_modules
    )

    build_reevaluation_plan(
        decision(),
        item,
        [trigger()],
    )

    assert item.invalidated_modules == before


def test_output_is_deterministic():
    first = build_reevaluation_plan(
        decision(),
        assessment(),
        [trigger()],
    )

    second = build_reevaluation_plan(
        decision(),
        assessment(),
        [trigger()],
    )

    assert first == second
