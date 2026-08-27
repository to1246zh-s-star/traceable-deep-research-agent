from models import (
    AdaptiveResearchIteration,
    AdaptiveResearchState,
    ReevaluationReactivationDecision,
    ResearchStoppingDecision,
)
from services.reevaluation_reactivation import (
    apply_reevaluation_reactivation,
)


def adaptive_state(
    *,
    status="stopped",
):
    return AdaptiveResearchState(
        decision_id="dec_test",
        iteration_count=1,
        max_iterations=3,
        executed_gap_ids=[
            "gap_old",
        ],
        executed_queries=[
            "old query",
        ],
        iterations=[
            AdaptiveResearchIteration(
                decision_id="dec_test",
                iteration_number=1,
                gap_ids=[
                    "gap_old",
                ],
                task_ids=[
                    1,
                ],
                status="completed",
            )
        ],
        status=status,
    )


def eligible():
    return ReevaluationReactivationDecision(
        decision_id="dec_test",
        status="ELIGIBLE",
        eligible=True,
        actionable_gap_ids=[
            "gap_reeval",
        ],
        remaining_iterations=2,
        remaining_tasks=6,
    )


def blocked():
    return ReevaluationReactivationDecision(
        decision_id="dec_test",
        status="BLOCKED",
        eligible=False,
        blocking_reasons=[
            "hard_stop:budget_exhausted",
        ],
    )


def stopping():
    return ResearchStoppingDecision(
        should_continue=False,
        reason="insufficient_marginal_improvement",
        readiness_score=0.61,
        readiness_status="CONFLICTED",
        readiness_improvement=0.01,
        actionable_gap_count=4,
        blocking_budget_limits=[],
        retrieval_yield_status="HIGH_YIELD",
        consecutive_low_yield_iterations=0,
        adaptive_research_value_status="MODERATE_VALUE",
        consecutive_low_value_iterations=0,
    )


def test_eligible_reactivation_sets_lifecycle_active():
    state = adaptive_state()

    new_state, new_stop = apply_reevaluation_reactivation(
        eligible(),
        state,
        stopping(),
    )

    assert new_state is state
    assert new_state.status == "active"

    assert new_stop is not None
    assert new_stop.should_continue is True
    assert new_stop.reason == "continue_research"


def test_reactivation_preserves_iteration_history():
    state = adaptive_state()

    before_count = state.iteration_count
    before_iterations = list(
        state.iterations
    )

    apply_reevaluation_reactivation(
        eligible(),
        state,
        stopping(),
    )

    assert state.iteration_count == before_count
    assert state.iterations == before_iterations


def test_reactivation_preserves_executed_gap_history():
    state = adaptive_state()

    before = list(
        state.executed_gap_ids
    )

    apply_reevaluation_reactivation(
        eligible(),
        state,
        stopping(),
    )

    assert state.executed_gap_ids == before


def test_reactivation_preserves_executed_query_history():
    state = adaptive_state()

    before = list(
        state.executed_queries
    )

    apply_reevaluation_reactivation(
        eligible(),
        state,
        stopping(),
    )

    assert state.executed_queries == before


def test_reactivation_preserves_stopping_metrics():
    state = adaptive_state()
    stop = stopping()

    _, reopened = apply_reevaluation_reactivation(
        eligible(),
        state,
        stop,
    )

    assert reopened is not None

    assert (
        reopened.readiness_score
        == stop.readiness_score
    )

    assert (
        reopened.readiness_status
        == stop.readiness_status
    )

    assert (
        reopened.readiness_improvement
        == stop.readiness_improvement
    )

    assert (
        reopened.actionable_gap_count
        == stop.actionable_gap_count
    )

    assert (
        reopened.retrieval_yield_status
        == stop.retrieval_yield_status
    )

    assert (
        reopened.adaptive_research_value_status
        == stop.adaptive_research_value_status
    )


def test_original_stopping_decision_is_not_mutated():
    state = adaptive_state()
    stop = stopping()

    original_reason = stop.reason
    original_continue = (
        stop.should_continue
    )

    _, reopened = apply_reevaluation_reactivation(
        eligible(),
        state,
        stop,
    )

    assert reopened is not stop

    assert (
        stop.should_continue
        == original_continue
    )

    assert stop.reason == original_reason


def test_blocked_reactivation_does_nothing():
    state = adaptive_state()
    stop = stopping()

    old_status = state.status

    new_state, new_stop = apply_reevaluation_reactivation(
        blocked(),
        state,
        stop,
    )

    assert new_state.status == old_status
    assert new_stop is stop

    assert stop.should_continue is False

    assert (
        stop.reason
        == "insufficient_marginal_improvement"
    )


def test_eligible_without_actionable_gaps_does_nothing():
    item = eligible()
    item.actionable_gap_ids = []

    state = adaptive_state()
    stop = stopping()

    new_state, new_stop = apply_reevaluation_reactivation(
        item,
        state,
        stop,
    )

    assert new_state.status == "stopped"
    assert new_stop is stop


def test_none_stopping_decision_only_reactivates_lifecycle():
    state = adaptive_state()

    new_state, new_stop = apply_reevaluation_reactivation(
        eligible(),
        state,
        None,
    )

    assert new_state.status == "active"
    assert new_stop is None


def test_decision_id_mismatch_is_rejected():
    item = eligible()
    item.decision_id = "dec_other"

    state = adaptive_state()

    try:
        apply_reevaluation_reactivation(
            item,
            state,
            stopping(),
        )
    except ValueError as exc:
        assert "decision_id" in str(exc)
    else:
        raise AssertionError(
            "expected decision_id mismatch"
        )


def test_apply_does_not_add_decision_outputs():
    state = adaptive_state()

    apply_reevaluation_reactivation(
        eligible(),
        state,
        stopping(),
    )

    assert not hasattr(
        state,
        "candidate_scores",
    )

    assert not hasattr(
        state,
        "recommendation",
    )

    assert not hasattr(
        state,
        "predicted_winner_id",
    )
