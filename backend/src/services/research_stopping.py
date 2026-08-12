"""Budget-aware adaptive stopping policy for V3 Phase 14."""

from models import (
    DecisionReadiness,
    ReadinessSnapshot,
    ResearchAnalysis,
    ResearchBudget,
    ResearchStoppingDecision,
    ResearchUsage,
)


DEFAULT_MIN_READINESS_IMPROVEMENT = 0.02


def budget_limit_violations(
    budget: ResearchBudget,
    usage: ResearchUsage,
) -> list[str]:
    """Return all exhausted research-budget dimensions."""

    violations: list[str] = []

    if usage.iterations >= budget.max_iterations:
        violations.append("max_iterations")

    if usage.tasks >= budget.max_tasks:
        violations.append("max_tasks")

    if (
        budget.max_searches is not None
        and usage.searches >= budget.max_searches
    ):
        violations.append("max_searches")

    if (
        budget.max_duration_seconds is not None
        and usage.duration_seconds >= budget.max_duration_seconds
    ):
        violations.append("max_duration_seconds")

    if (
        budget.max_tokens is not None
        and usage.tokens >= budget.max_tokens
    ):
        violations.append("max_tokens")

    if (
        budget.max_cost is not None
        and usage.cost >= budget.max_cost
    ):
        violations.append("max_cost")

    return violations


def calculate_readiness_improvement(
    history: list[ReadinessSnapshot],
) -> float | None:
    """
    Return improvement between the latest two readiness snapshots.

    None means there is not yet enough history to estimate marginal gain.
    """

    if len(history) < 2:
        return None

    return (
        history[-1].overall_score
        - history[-2].overall_score
    )


def count_actionable_gaps(
    analysis: ResearchAnalysis,
) -> int:
    """Count currently open gaps that provide a follow-up query."""

    return sum(
        1
        for gap in analysis.research_gaps
        if (
            gap.status == "open"
            and bool((gap.suggested_query or "").strip())
        )
    )


def should_continue_research(
    readiness: DecisionReadiness,
    analysis: ResearchAnalysis,
    budget: ResearchBudget,
    usage: ResearchUsage,
    *,
    readiness_history: list[ReadinessSnapshot] | None = None,
    min_readiness_improvement: float = DEFAULT_MIN_READINESS_IMPROVEMENT,
) -> ResearchStoppingDecision:
    """
    Decide whether another adaptive research iteration is justified.

    Priority order:

    1. READY -> stop.
    2. Exhausted budget -> stop.
    3. No actionable research gaps -> stop.
    4. Repeatedly weak readiness improvement -> stop.
    5. Otherwise -> continue.
    """

    history = readiness_history or []

    improvement = calculate_readiness_improvement(
        history
    )

    actionable_gap_count = count_actionable_gaps(
        analysis
    )

    budget_violations = budget_limit_violations(
        budget,
        usage,
    )

    if readiness.status == "READY":
        return ResearchStoppingDecision(
            should_continue=False,
            reason="decision_ready",
            readiness_score=readiness.overall_score,
            readiness_status=readiness.status,
            readiness_improvement=improvement,
            actionable_gap_count=actionable_gap_count,
            blocking_budget_limits=[],
        )

    if budget_violations:
        return ResearchStoppingDecision(
            should_continue=False,
            reason="budget_exhausted",
            readiness_score=readiness.overall_score,
            readiness_status=readiness.status,
            readiness_improvement=improvement,
            actionable_gap_count=actionable_gap_count,
            blocking_budget_limits=budget_violations,
        )

    if actionable_gap_count == 0:
        return ResearchStoppingDecision(
            should_continue=False,
            reason="no_actionable_gaps",
            readiness_score=readiness.overall_score,
            readiness_status=readiness.status,
            readiness_improvement=improvement,
            actionable_gap_count=0,
            blocking_budget_limits=[],
        )

    if (
        improvement is not None
        and improvement < min_readiness_improvement
    ):
        return ResearchStoppingDecision(
            should_continue=False,
            reason="insufficient_marginal_improvement",
            readiness_score=readiness.overall_score,
            readiness_status=readiness.status,
            readiness_improvement=improvement,
            actionable_gap_count=actionable_gap_count,
            blocking_budget_limits=[],
        )

    return ResearchStoppingDecision(
        should_continue=True,
        reason="continue_research",
        readiness_score=readiness.overall_score,
        readiness_status=readiness.status,
        readiness_improvement=improvement,
        actionable_gap_count=actionable_gap_count,
        blocking_budget_limits=[],
    )
