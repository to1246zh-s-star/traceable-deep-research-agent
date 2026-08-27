"""Deterministic arbitration between legacy readiness stopping and research value."""

from __future__ import annotations

from dataclasses import replace

from models import (
    AdaptiveResearchState,
    ResearchBudget,
    ResearchStoppingDecision,
    ResearchUsage,
)


SOFT_STOP_REASONS = {
    "insufficient_marginal_improvement",
}

USEFUL_RESEARCH_VALUE_STATUSES = {
    "HIGH_VALUE",
    "MODERATE_VALUE",
}


def arbitrate_adaptive_stopping(
    stopping: ResearchStoppingDecision | None,
    adaptive_state: AdaptiveResearchState,
    budget: ResearchBudget,
    usage: ResearchUsage,
) -> ResearchStoppingDecision | None:
    """
    Reconcile legacy readiness-improvement stopping with adaptive research value.

    Only the legacy weak-improvement stop is treated as soft.

    Hard stops remain untouched:
    - decision ready
    - exhausted budget
    - no actionable gaps
    - diminishing returns from unified research value
    - any unknown/new stopping reason

    A soft stop may be reopened only when:
    - latest adaptive iteration produced HIGH/MODERATE research value,
    - actionable gaps remain,
    - iteration/task budget remains,
    - no explicit blocking budget limit was reported.
    """

    if stopping is None:
        return None

    if stopping.should_continue:
        return stopping

    if stopping.reason not in SOFT_STOP_REASONS:
        return stopping

    if not adaptive_state.iterations:
        return stopping

    latest = adaptive_state.iterations[-1]

    value_status = str(
        getattr(
            latest,
            "adaptive_research_value_status",
            "UNKNOWN",
        )
        or "UNKNOWN"
    ).upper()

    if value_status not in USEFUL_RESEARCH_VALUE_STATUSES:
        return stopping

    if stopping.actionable_gap_count <= 0:
        return stopping

    if stopping.blocking_budget_limits:
        return stopping

    effective_max_iterations = min(
        adaptive_state.max_iterations,
        budget.max_iterations,
    )

    if adaptive_state.iteration_count >= effective_max_iterations:
        return stopping

    if usage.tasks >= budget.max_tasks:
        return stopping

    return replace(
        stopping,
        should_continue=True,
        reason="continue_research",
    )


def finalize_adaptive_research_state(
    adaptive_state: AdaptiveResearchState,
    stopping: ResearchStoppingDecision | None,
) -> AdaptiveResearchState:
    """
    Keep adaptive lifecycle state consistent with the final stopping decision.

    Existing planner terminal states such as budget_exhausted and
    no_actionable_gaps are preserved. Only an otherwise-active state is
    transitioned to stopped when research has actually been told to stop.
    """

    if (
        stopping is not None
        and not stopping.should_continue
        and adaptive_state.status == "active"
    ):
        adaptive_state.status = "stopped"

    return adaptive_state
