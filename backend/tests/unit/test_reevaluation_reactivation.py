from models import (
    AdaptiveResearchState,
    ReevaluationPlan,
    ResearchBudget,
    ResearchGap,
    ResearchStoppingDecision,
    ResearchUsage,
)
from services.reevaluation_reactivation import (
    assess_reevaluation_reactivation,
)


def plan(
    status="REQUIRED",
):
    return ReevaluationPlan(
        decision_id="dec_test",
        status=status,
        research_queries=[
            "updated deployment evidence"
        ],
    )


def gap(
    *,
    gap_id="gap_reeval",
    query="updated deployment evidence",
):
    return ResearchGap(
        gap_id=gap_id,
        candidate_id="",
        criterion_id="",
        gap_type="reevaluation",
        severity=1.0,
        priority=3,
        description="Re-evaluate deployment context",
        suggested_query=query,
        status="open",
    )


def adaptive_state(
    *,
    status="stopped",
    iteration_count=1,
):
    return AdaptiveResearchState(
        decision_id="dec_test",
        status=status,
        iteration_count=iteration_count,
        max_iterations=3,
    )


def stopping(
    reason="insufficient_marginal_improvement",
):
    return ResearchStoppingDecision(
        should_continue=False,
        reason=reason,
        readiness_score=0.6,
        readiness_status="CONFLICTED",
        actionable_gap_count=1,
        blocking_budget_limits=[],
    )


def budget():
    return ResearchBudget(
        max_iterations=3,
        max_tasks=9,
    )


def usage():
    return ResearchUsage(
        iterations=1,
        tasks=3,
    )


def test_required_soft_stopped_state_is_eligible():
    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.status == "ELIGIBLE"
    assert result.eligible is True
    assert result.actionable_gap_ids == [
        "gap_reeval"
    ]

    assert result.remaining_iterations == 2
    assert result.remaining_tasks == 6


def test_recommended_does_not_reopen():
    result = assess_reevaluation_reactivation(
        plan("RECOMMENDED"),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.status == "BLOCKED"
    assert result.eligible is False

    assert (
        "reevaluation_status_not_required"
        in result.blocking_reasons
    )


def test_unknown_does_not_reopen():
    result = assess_reevaluation_reactivation(
        plan("UNKNOWN"),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.eligible is False


def test_not_required_does_not_reopen():
    result = assess_reevaluation_reactivation(
        plan("NOT_REQUIRED"),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.eligible is False


def test_already_active_state_is_not_reactivated():
    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        adaptive_state(
            status="active"
        ),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.status == "BLOCKED"

    assert (
        "adaptive_research_already_active"
        in result.blocking_reasons
    )


def test_budget_exhausted_stop_is_hard_block():
    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(
            "budget_exhausted"
        ),
    )

    assert result.eligible is False
    assert (
        "hard_stop:budget_exhausted"
        in result.blocking_reasons
    )


def test_diminishing_returns_is_hard_block():
    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(
            "diminishing_returns"
        ),
    )

    assert result.eligible is False


def test_decision_ready_is_hard_block_for_same_lifecycle():
    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(
            "decision_ready"
        ),
    )

    assert result.eligible is False

    assert (
        "hard_stop:decision_ready"
        in result.blocking_reasons
    )


def test_iteration_budget_exhaustion_blocks():
    state = adaptive_state(
        iteration_count=3
    )

    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        state,
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.eligible is False

    assert (
        "iteration_budget_exhausted"
        in result.blocking_reasons
    )


def test_task_budget_exhaustion_blocks():
    exhausted_usage = ResearchUsage(
        iterations=1,
        tasks=9,
    )

    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        adaptive_state(),
        research_budget=budget(),
        research_usage=exhausted_usage,
        stopping_decision=stopping(),
    )

    assert result.eligible is False

    assert (
        "task_budget_exhausted"
        in result.blocking_reasons
    )


def test_no_current_actionable_gap_blocks():
    result = assess_reevaluation_reactivation(
        plan(),
        [],
        adaptive_state(),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.eligible is False

    assert (
        "no_actionable_reevaluation_gaps"
        in result.blocking_reasons
    )


def test_historical_no_actionable_gap_can_be_superseded():
    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        adaptive_state(
            status="no_actionable_gaps"
        ),
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(
            "no_actionable_gaps"
        ),
    )

    # New externally-triggered gap exists now, so an old
    # no_actionable_gaps state is not itself a permanent truth.
    assert result.eligible is True


def test_executed_query_is_not_actionable_again():
    state = adaptive_state()
    state.executed_queries = [
        "updated deployment evidence"
    ]

    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        state,
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.eligible is False

    assert (
        "no_actionable_reevaluation_gaps"
        in result.blocking_reasons
    )


def test_executed_gap_is_not_actionable_again():
    state = adaptive_state()
    state.executed_gap_ids = [
        "gap_reeval"
    ]

    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        state,
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.eligible is False


def test_evaluator_does_not_mutate_lifecycle():
    state = adaptive_state()
    stop = stopping()

    original_status = state.status
    original_should_continue = (
        stop.should_continue
    )
    original_reason = stop.reason

    result = assess_reevaluation_reactivation(
        plan(),
        [gap()],
        state,
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stop,
    )

    assert result.eligible is True

    assert state.status == original_status

    assert (
        stop.should_continue
        == original_should_continue
    )

    assert stop.reason == original_reason


def test_decision_id_mismatch_is_rejected():
    item = plan()
    item.decision_id = "dec_other"

    try:
        assess_reevaluation_reactivation(
            item,
            [gap()],
            adaptive_state(),
            research_budget=budget(),
            research_usage=usage(),
            stopping_decision=stopping(),
        )
    except ValueError as exc:
        assert "decision_id" in str(exc)
    else:
        raise AssertionError(
            "expected decision_id mismatch"
        )
