"""Deterministic eligibility policy for reactivating adaptive research."""

from __future__ import annotations

from models import (
    AdaptiveResearchState,
    ReevaluationPlan,
    ReevaluationReactivationDecision,
    ResearchBudget,
    ResearchGap,
    ResearchStoppingDecision,
    ResearchUsage,
)
from services.adaptive_research import (
    select_research_gaps,
)


HARD_STOP_REASONS = {
    "decision_ready",
    "budget_exhausted",
    "diminishing_returns",
}


def assess_reevaluation_reactivation(
    plan: ReevaluationPlan,
    gaps: list[ResearchGap],
    adaptive_state: AdaptiveResearchState,
    *,
    research_budget: ResearchBudget | None,
    research_usage: ResearchUsage | None,
    stopping_decision: ResearchStoppingDecision | None,
) -> ReevaluationReactivationDecision:
    """
    Determine whether an existing adaptive lifecycle is eligible to reopen.

    This function never mutates:
    - adaptive_state;
    - stopping_decision;
    - research budget / usage;
    - research gaps;
    - decision scores or recommendations.
    """

    if plan.decision_id != adaptive_state.decision_id:
        raise ValueError(
            "reevaluation plan decision_id does not match adaptive state"
        )

    result = ReevaluationReactivationDecision(
        decision_id=plan.decision_id,
    )

    if plan.status != "REQUIRED":
        result.status = "BLOCKED"
        result.blocking_reasons.append(
            "reevaluation_status_not_required"
        )
        return result

    if adaptive_state.status == "active":
        result.status = "BLOCKED"
        result.blocking_reasons.append(
            "adaptive_research_already_active"
        )
        return result

    stopping_reason = (
        stopping_decision.reason
        if stopping_decision is not None
        else None
    )

    if stopping_reason in HARD_STOP_REASONS:
        result.status = "BLOCKED"
        result.blocking_reasons.append(
            f"hard_stop:{stopping_reason}"
        )
        return _attach_remaining_budget(
            result,
            adaptive_state,
            research_budget,
            research_usage,
        )

    result = _attach_remaining_budget(
        result,
        adaptive_state,
        research_budget,
        research_usage,
    )

    if (
        result.remaining_iterations is not None
        and result.remaining_iterations <= 0
    ):
        result.status = "BLOCKED"
        result.blocking_reasons.append(
            "iteration_budget_exhausted"
        )
        return result

    if (
        result.remaining_tasks is not None
        and result.remaining_tasks <= 0
    ):
        result.status = "BLOCKED"
        result.blocking_reasons.append(
            "task_budget_exhausted"
        )
        return result

    max_tasks = (
        result.remaining_tasks
        if result.remaining_tasks is not None
        else 3
    )

    if max_tasks <= 0:
        result.status = "BLOCKED"
        result.blocking_reasons.append(
            "no_task_capacity"
        )
        return result

    # Reuse the existing adaptive selector so status=open,
    # executed gap IDs, executed query dedupe and strategy rerouting
    # semantics remain authoritative.
    actionable = select_research_gaps(
        _analysis_for_selection(
            plan.decision_id,
            gaps,
        ),
        adaptive_state,
        max_tasks=max_tasks,
    )

    result.actionable_gap_ids = [
        gap.gap_id
        for gap in actionable
    ]

    if not actionable:
        result.status = "BLOCKED"
        result.blocking_reasons.append(
            "no_actionable_reevaluation_gaps"
        )
        return result

    result.status = "ELIGIBLE"
    result.eligible = True

    return result


def _attach_remaining_budget(
    result: ReevaluationReactivationDecision,
    adaptive_state: AdaptiveResearchState,
    research_budget: ResearchBudget | None,
    research_usage: ResearchUsage | None,
) -> ReevaluationReactivationDecision:
    if research_budget is not None:
        effective_max_iterations = min(
            adaptive_state.max_iterations,
            research_budget.max_iterations,
        )

        result.remaining_iterations = max(
            0,
            effective_max_iterations
            - adaptive_state.iteration_count,
        )

    if (
        research_budget is not None
        and research_usage is not None
    ):
        result.remaining_tasks = max(
            0,
            research_budget.max_tasks
            - research_usage.tasks,
        )

    return result


def _analysis_for_selection(
    decision_id: str,
    gaps: list[ResearchGap],
):
    # Local import avoids adding another business model solely for
    # eligibility evaluation.
    from models import ResearchAnalysis

    return ResearchAnalysis(
        decision_id=decision_id,
        research_gaps=list(gaps),
    )


def apply_reevaluation_reactivation(
    reactivation: ReevaluationReactivationDecision,
    adaptive_state: AdaptiveResearchState,
    stopping_decision: ResearchStoppingDecision | None,
) -> tuple[
    AdaptiveResearchState,
    ResearchStoppingDecision | None,
]:
    """
    Apply an already-authorized re-evaluation reactivation.

    This is intentionally a very small orchestration mutation.

    It may:
    - transition the adaptive lifecycle back to active;
    - reopen the orchestration stopping gate.

    It must never:
    - reset iteration history;
    - reset executed gap/query history;
    - reset budget or usage;
    - alter readiness metrics;
    - change candidate comparison;
    - create candidate scores;
    - change structured recommendation.
    """

    if (
        reactivation.decision_id
        != adaptive_state.decision_id
    ):
        raise ValueError(
            "reactivation decision_id does not match adaptive state"
        )

    if (
        reactivation.status != "ELIGIBLE"
        or not reactivation.eligible
    ):
        return (
            adaptive_state,
            stopping_decision,
        )

    if not reactivation.actionable_gap_ids:
        # Defensive boundary: an ELIGIBLE record without actionable
        # work must not reopen execution.
        return (
            adaptive_state,
            stopping_decision,
        )

    adaptive_state.status = "active"

    if stopping_decision is None:
        return (
            adaptive_state,
            None,
        )

    # Preserve all historical/readiness fields. Only the orchestration
    # continue gate changes.
    from dataclasses import replace

    reopened_stopping = replace(
        stopping_decision,
        should_continue=True,
        reason="continue_research",
    )

    return (
        adaptive_state,
        reopened_stopping,
    )


def apply_reevaluation_reactivation(
    reactivation: ReevaluationReactivationDecision,
    adaptive_state: AdaptiveResearchState,
    stopping_decision: ResearchStoppingDecision | None,
) -> tuple[
    AdaptiveResearchState,
    ResearchStoppingDecision | None,
]:
    """
    Apply an already-authorized re-evaluation reactivation.

    This is intentionally a very small orchestration mutation.

    It may:
    - transition the adaptive lifecycle back to active;
    - reopen the orchestration stopping gate.

    It must never:
    - reset iteration history;
    - reset executed gap/query history;
    - reset budget or usage;
    - alter readiness metrics;
    - change candidate comparison;
    - create candidate scores;
    - change structured recommendation.
    """

    if (
        reactivation.decision_id
        != adaptive_state.decision_id
    ):
        raise ValueError(
            "reactivation decision_id does not match adaptive state"
        )

    if (
        reactivation.status != "ELIGIBLE"
        or not reactivation.eligible
    ):
        return (
            adaptive_state,
            stopping_decision,
        )

    if not reactivation.actionable_gap_ids:
        # Defensive boundary: an ELIGIBLE record without actionable
        # work must not reopen execution.
        return (
            adaptive_state,
            stopping_decision,
        )

    adaptive_state.status = "active"

    if stopping_decision is None:
        return (
            adaptive_state,
            None,
        )

    # Preserve all historical/readiness fields. Only the orchestration
    # continue gate changes.
    from dataclasses import replace

    reopened_stopping = replace(
        stopping_decision,
        should_continue=True,
        reason="continue_research",
    )

    return (
        adaptive_state,
        reopened_stopping,
    )
