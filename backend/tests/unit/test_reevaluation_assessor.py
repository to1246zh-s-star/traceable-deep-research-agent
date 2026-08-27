from models import (
    DecisionReevaluationTrigger,
    ReevaluationRequest,
)
from services.reevaluation_assessor import (
    assess_reevaluation_need,
)


def make_trigger(
    *,
    trigger_id="trg_context",
    decision_id="dec_test",
    source_type="technical_context",
    source_field="deployment_environment",
    trigger_type="TECHNICAL_CONTEXT_CHANGE",
    trigger_impact="HIGH",
    reevaluation_required=True,
):
    return DecisionReevaluationTrigger(
        trigger_id=trigger_id,
        decision_id=decision_id,
        trigger_type=trigger_type,
        source_type=source_type,
        source_field=source_field,
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
        trigger_impact=trigger_impact,
        reevaluation_required=(
            reevaluation_required
        ),
        rationale=[
            "Deployment context changed."
        ],
    )


def test_exact_trigger_id_requires_reevaluation():
    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_context",
        ],
    )

    result = assess_reevaluation_need(
        request,
        [make_trigger()],
    )

    assert result.status == "REQUIRED"
    assert result.matched_trigger_ids == [
        "trg_context"
    ]

    assert result.invalidated_modules == [
        "integration_assessment",
        "scenario_analysis",
    ]


def test_structured_source_field_matches_trigger():
    request = ReevaluationRequest(
        decision_id="dec_test",
        changed_source_fields={
            "technical_context": [
                "deployment_environment",
            ]
        },
    )

    result = assess_reevaluation_need(
        request,
        [make_trigger()],
    )

    assert result.status == "REQUIRED"

    assert result.affected_candidate_ids == [
        "cand_a",
        "cand_b",
    ]

    assert result.affected_criterion_ids == [
        "crit_ops",
    ]

    assert result.affected_scenario_ids == [
        "scn_arch",
    ]


def test_matched_non_required_trigger_is_recommended():
    trigger = make_trigger(
        trigger_id="trg_low",
        trigger_impact="LOW",
        reevaluation_required=False,
    )

    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_low",
        ],
    )

    result = assess_reevaluation_need(
        request,
        [trigger],
    )

    assert result.status == (
        "RECOMMENDED"
    )


def test_structured_change_without_matching_trigger_is_not_required():
    request = ReevaluationRequest(
        decision_id="dec_test",
        changed_source_fields={
            "technical_context": [
                "team_capabilities",
            ]
        },
    )

    result = assess_reevaluation_need(
        request,
        [make_trigger()],
    )

    assert result.status == (
        "NOT_REQUIRED"
    )
    assert result.matched_trigger_ids == []


def test_no_structured_observation_is_unknown():
    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_facts=[
            "Deployment might change."
        ],
    )

    result = assess_reevaluation_need(
        request,
        [make_trigger()],
    )

    assert result.status == "UNKNOWN"
    assert result.matched_trigger_ids == []


def test_free_text_facts_never_match_trigger():
    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_facts=[
            (
                "The deployment environment changed "
                "from Docker to Kubernetes."
            )
        ],
    )

    result = assess_reevaluation_need(
        request,
        [make_trigger()],
    )

    assert result.status == "UNKNOWN"


def test_other_decision_triggers_are_ignored():
    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_other",
        ],
    )

    trigger = make_trigger(
        trigger_id="trg_other",
        decision_id="dec_other",
    )

    result = assess_reevaluation_need(
        request,
        [trigger],
    )

    assert result.status == (
        "NOT_REQUIRED"
    )
    assert result.matched_trigger_ids == []


def test_duplicate_invalidated_modules_are_deduplicated():
    first = make_trigger(
        trigger_id="trg_1",
    )

    second = make_trigger(
        trigger_id="trg_2",
        source_field="existing_stack",
    )

    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_1",
            "trg_2",
        ],
    )

    result = assess_reevaluation_need(
        request,
        [
            first,
            second,
        ],
    )

    assert result.status == "REQUIRED"

    assert result.invalidated_modules == [
        "integration_assessment",
        "scenario_analysis",
    ]


def test_trigger_rationale_is_preserved():
    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_context",
        ],
    )

    result = assess_reevaluation_need(
        request,
        [make_trigger()],
    )

    assert (
        "Deployment context changed."
        in result.reasons
    )


def test_assessment_does_not_synthesize_scores_or_winner():
    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_context",
        ],
    )

    result = assess_reevaluation_need(
        request,
        [make_trigger()],
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


def test_inputs_are_not_mutated():
    trigger = make_trigger()

    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_context",
        ],
    )

    original_modules = list(
        trigger.invalidated_modules
    )

    assess_reevaluation_need(
        request,
        [trigger],
    )

    assert trigger.invalidated_modules == (
        original_modules
    )


def test_output_is_deterministic():
    triggers = [
        make_trigger(
            trigger_id="trg_b",
        ),
        make_trigger(
            trigger_id="trg_a",
        ),
    ]

    request = ReevaluationRequest(
        decision_id="dec_test",
        observed_trigger_ids=[
            "trg_b",
            "trg_a",
        ],
    )

    first = assess_reevaluation_need(
        request,
        triggers,
    )

    second = assess_reevaluation_need(
        request,
        triggers,
    )

    assert first == second

    assert first.matched_trigger_ids == [
        "trg_a",
        "trg_b",
    ]
