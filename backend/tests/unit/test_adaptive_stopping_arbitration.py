from models import (
    AdaptiveResearchIteration,
    AdaptiveResearchState,
    ResearchBudget,
    ResearchStoppingDecision,
    ResearchUsage,
)
from services.adaptive_stopping_arbitration import (
    arbitrate_adaptive_stopping,
    finalize_adaptive_research_state,
)


def stopping(
    *,
    should_continue=False,
    reason="insufficient_marginal_improvement",
    gaps=3,
    blocking=None,
):
    return ResearchStoppingDecision(
        should_continue=should_continue,
        reason=reason,
        readiness_score=0.6,
        readiness_status="CONFLICTED",
        readiness_improvement=0.01,
        actionable_gap_count=gaps,
        blocking_budget_limits=blocking or [],
    )


def adaptive_state(
    *,
    value="MODERATE_VALUE",
    iteration_count=2,
    status="active",
):
    return AdaptiveResearchState(
        decision_id="dec_test",
        iteration_count=iteration_count,
        max_iterations=3,
        status=status,
        iterations=[
            AdaptiveResearchIteration(
                decision_id="dec_test",
                iteration_number=iteration_count,
                status="completed",
                adaptive_research_value_status=value,
            )
        ],
    )


def test_useful_research_value_reopens_soft_readiness_stop():
    result = arbitrate_adaptive_stopping(
        stopping(),
        adaptive_state(
            value="MODERATE_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is True
    assert result.reason == "continue_research"


def test_high_value_also_reopens_soft_stop():
    result = arbitrate_adaptive_stopping(
        stopping(),
        adaptive_state(
            value="HIGH_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is True


def test_low_value_does_not_reopen_soft_stop():
    result = arbitrate_adaptive_stopping(
        stopping(),
        adaptive_state(
            value="LOW_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is False
    assert (
        result.reason
        == "insufficient_marginal_improvement"
    )


def test_unknown_value_does_not_reopen_soft_stop():
    result = arbitrate_adaptive_stopping(
        stopping(),
        adaptive_state(
            value="UNKNOWN",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is False


def test_diminishing_returns_is_preserved():
    result = arbitrate_adaptive_stopping(
        stopping(
            reason="diminishing_returns",
        ),
        adaptive_state(
            value="HIGH_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is False
    assert result.reason == "diminishing_returns"


def test_other_strong_stop_is_preserved():
    result = arbitrate_adaptive_stopping(
        stopping(
            reason="decision_ready",
        ),
        adaptive_state(
            value="HIGH_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is False
    assert result.reason == "decision_ready"


def test_no_actionable_gaps_prevents_reopen():
    result = arbitrate_adaptive_stopping(
        stopping(
            gaps=0,
        ),
        adaptive_state(
            value="HIGH_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is False


def test_iteration_budget_exhaustion_prevents_reopen():
    result = arbitrate_adaptive_stopping(
        stopping(),
        adaptive_state(
            value="HIGH_VALUE",
            iteration_count=3,
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=3,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is False


def test_task_budget_exhaustion_prevents_reopen():
    result = arbitrate_adaptive_stopping(
        stopping(),
        adaptive_state(
            value="HIGH_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=9,
        ),
    )

    assert result is not None
    assert result.should_continue is False


def test_explicit_blocking_budget_prevents_reopen():
    result = arbitrate_adaptive_stopping(
        stopping(
            blocking=["max_duration_seconds"],
        ),
        adaptive_state(
            value="HIGH_VALUE",
        ),
        ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        ResearchUsage(
            iterations=2,
            tasks=6,
        ),
    )

    assert result is not None
    assert result.should_continue is False


def test_finalizer_marks_active_state_stopped():
    state = adaptive_state(
        status="active",
    )

    finalize_adaptive_research_state(
        state,
        stopping(
            reason="diminishing_returns",
        ),
    )

    assert state.status == "stopped"


def test_finalizer_preserves_budget_exhausted():
    state = adaptive_state(
        status="budget_exhausted",
    )

    finalize_adaptive_research_state(
        state,
        stopping(
            reason="budget_exhausted",
        ),
    )

    assert state.status == "budget_exhausted"


def test_finalizer_preserves_no_actionable_gaps():
    state = adaptive_state(
        status="no_actionable_gaps",
    )

    finalize_adaptive_research_state(
        state,
        stopping(
            reason="no_actionable_gaps",
        ),
    )

    assert state.status == "no_actionable_gaps"


def test_finalizer_keeps_active_while_research_continues():
    state = adaptive_state(
        status="active",
    )

    finalize_adaptive_research_state(
        state,
        stopping(
            should_continue=True,
            reason="continue_research",
        ),
    )

    assert state.status == "active"
