"""High-level orchestration for adaptive decision research."""

from __future__ import annotations

from typing import Callable

from models import (
    AdaptiveResearchState,
    ResearchBudget,
    ResearchUsage,
    SummaryState,
)


def ensure_adaptive_runtime(
    state: SummaryState,
) -> tuple[
    ResearchBudget,
    ResearchUsage,
    AdaptiveResearchState,
]:
    """
    Return persistent runtime objects for one adaptive decision workflow.

    Existing objects on SummaryState are reused so budget accounting is
    cumulative across repeated decision-intelligence passes.
    """

    decision = state.decision_case

    if decision is None:
        raise ValueError(
            "adaptive decision runtime requires decision_case"
        )

    budget = state.research_budget

    if budget is None:
        budget = ResearchBudget()
        state.research_budget = budget

    usage = state.research_usage

    if usage is None:
        usage = ResearchUsage()
        state.research_usage = usage

    adaptive_state = state.adaptive_research_state

    if adaptive_state is None:
        adaptive_state = AdaptiveResearchState(
            decision_id=decision.decision_id,
            max_iterations=budget.max_iterations,
        )
        state.adaptive_research_state = adaptive_state

    return budget, usage, adaptive_state


def record_adaptive_iteration_usage(
    usage: ResearchUsage,
    *,
    task_count: int,
) -> None:
    """
    Record resource usage after one executed adaptive iteration.

    Only metrics that are observable at this orchestration boundary are
    updated here. Search/token/cost accounting can be connected later to
    their real instrumentation sources.
    """

    if task_count < 0:
        raise ValueError(
            "task_count must be non-negative"
        )

    usage.iterations += 1
    usage.tasks += task_count


def run_adaptive_decision_loop(
    state: SummaryState,
    *,
    execute_followups: Callable,
    execute_decision_intelligence: Callable,
    max_tasks_per_iteration: int = 3,
) -> SummaryState:
    """
    Execute bounded adaptive research until the current stopping decision
    says to stop or no follow-up iteration can be planned.

    The caller supplies the Agent bridge methods so this service remains
    independent from DeepResearchAgent.
    """

    if state.decision_case is None:
        return state

    budget, usage, adaptive_state = ensure_adaptive_runtime(
        state
    )

    while True:
        stopping = state.stopping_decision

        if stopping is None:
            break

        if not stopping.should_continue:
            break

        analysis = state.research_analysis

        if analysis is None:
            break

        iteration = execute_followups(
            state,
            analysis,
            adaptive_state,
            max_tasks=max_tasks_per_iteration,
        )

        if iteration is None:
            break

        record_adaptive_iteration_usage(
            usage,
            task_count=len(iteration.task_ids),
        )

        execute_decision_intelligence(
            state,
            research_budget=budget,
            research_usage=usage,
        )

    return state
