"""Adaptive replanning baseline for V3 Phase 12."""

from models import (
    AdaptiveResearchIteration,
    AdaptiveResearchState,
    ResearchAnalysis,
    ResearchBudget,
    ResearchGap,
    ResearchUsage,
    TodoItem,
)

from services.strategy_replanning import (
    build_effective_followup_query,
    is_strategy_reroute,
)


DEFAULT_MAX_FOLLOWUP_TASKS = 3


def normalize_query(query: str) -> str:
    """Normalize queries for deterministic duplicate detection."""

    return " ".join(
        query.lower().strip().split()
    )


def select_research_gaps(
    analysis: ResearchAnalysis,
    adaptive_state: AdaptiveResearchState,
    *,
    max_tasks: int = DEFAULT_MAX_FOLLOWUP_TASKS,
) -> list[ResearchGap]:
    """
    Select the highest-severity unresolved research gaps.

    Previously executed gaps and duplicate queries are excluded.
    """

    if max_tasks <= 0:
        return []

    executed_gap_ids = set(
        adaptive_state.executed_gap_ids
    )

    executed_queries = {
        normalize_query(query)
        for query in adaptive_state.executed_queries
    }

    selected: list[ResearchGap] = []
    selected_queries: set[str] = set()

    for gap in sorted(
        analysis.research_gaps,
        key=lambda item: (
            -item.priority,
            -item.severity,
            item.gap_id,
        ),
    ):
        if gap.status != "open":
            continue

        if (
            gap.gap_id in executed_gap_ids
            and not is_strategy_reroute(gap)
        ):
            continue

        effective_query = (
            build_effective_followup_query(
                gap
            )
        )

        if not effective_query:
            continue

        normalized_query = normalize_query(
            effective_query
        )

        if not normalized_query:
            continue

        if normalized_query in executed_queries:
            continue

        if normalized_query in selected_queries:
            continue

        selected.append(gap)
        selected_queries.add(normalized_query)

        if len(selected) >= max_tasks:
            break

    return selected


def create_followup_tasks(
    gaps: list[ResearchGap],
    *,
    starting_task_id: int,
) -> list[TodoItem]:
    """Convert selected gaps into strategy-aware executable tasks."""

    tasks: list[TodoItem] = []

    for gap in gaps:
        query = (
            build_effective_followup_query(
                gap
            )
        )

        if not query:
            continue

        task_id = (
            starting_task_id
            + len(tasks)
            + 1
        )

        missing_types = (
            ", ".join(
                gap.missing_source_types
            )
            if gap.missing_source_types
            else None
        )

        intent = (
            "Resolve adaptive research gap "
            f"{gap.gap_id}: "
            f"{gap.description}"
        )

        if missing_types:
            intent += (
                ". Target missing source "
                f"types: {missing_types}"
            )

        tasks.append(
            TodoItem(
                id=task_id,
                title=(
                    "Follow-up research: "
                    f"{gap.gap_type}"
                ),
                intent=intent,
                query=query,
            )
        )

    return tasks


def plan_adaptive_iteration(
    analysis: ResearchAnalysis,
    adaptive_state: AdaptiveResearchState,
    *,
    starting_task_id: int,
    max_tasks: int = DEFAULT_MAX_FOLLOWUP_TASKS,
    research_budget: ResearchBudget | None = None,
    research_usage: ResearchUsage | None = None,
) -> tuple[
    AdaptiveResearchIteration | None,
    list[TodoItem],
]:
    """
    Plan one bounded adaptive research iteration.

    Returns (None, []) when stopping conditions are met.
    """

    if adaptive_state.status != "active":
        return None, []

    effective_max_iterations = adaptive_state.max_iterations

    if research_budget is not None:
        effective_max_iterations = min(
            effective_max_iterations,
            research_budget.max_iterations,
        )

    if (
        adaptive_state.iteration_count
        >= effective_max_iterations
    ):
        adaptive_state.status = "budget_exhausted"
        return None, []

    if (
        research_budget is not None
        and research_usage is not None
    ):
        if research_usage.tasks >= research_budget.max_tasks:
            adaptive_state.status = "budget_exhausted"
            return None, []

        remaining_tasks = (
            research_budget.max_tasks
            - research_usage.tasks
        )

        max_tasks = min(
            max_tasks,
            remaining_tasks,
        )

        if max_tasks <= 0:
            adaptive_state.status = "budget_exhausted"
            return None, []

    gaps = select_research_gaps(
        analysis,
        adaptive_state,
        max_tasks=max_tasks,
    )

    if not gaps:
        adaptive_state.status = "no_actionable_gaps"
        return None, []

    tasks = create_followup_tasks(
        gaps,
        starting_task_id=starting_task_id,
    )

    iteration_number = (
        adaptive_state.iteration_count + 1
    )

    iteration = AdaptiveResearchIteration(
        decision_id=adaptive_state.decision_id,
        iteration_number=iteration_number,
        gap_ids=[
            gap.gap_id
            for gap in gaps
        ],
        task_ids=[
            task.id
            for task in tasks
        ],
        status="planned",
    )

    return iteration, tasks


def record_iteration_started(
    adaptive_state: AdaptiveResearchState,
    iteration: AdaptiveResearchIteration,
    gaps: list[ResearchGap],
) -> None:
    """Record one adaptive iteration before task execution."""

    if iteration.status != "planned":
        raise ValueError(
            "iteration must be planned before it can start"
        )

    iteration.status = "running"

    adaptive_state.iteration_count += 1
    adaptive_state.iterations.append(iteration)

    for gap in gaps:
        if gap.gap_id not in adaptive_state.executed_gap_ids:
            adaptive_state.executed_gap_ids.append(
                gap.gap_id
            )

        effective_query = (
            build_effective_followup_query(
                gap
            )
        )

        if effective_query:
            normalized = normalize_query(
                effective_query
            )

            existing = {
                normalize_query(query)
                for query
                in adaptive_state.executed_queries
            }

            if normalized not in existing:
                adaptive_state.executed_queries.append(
                    effective_query
                )


def record_iteration_finished(
    adaptive_state: AdaptiveResearchState,
    iteration: AdaptiveResearchIteration,
    *,
    success: bool,
) -> None:
    """Finalize adaptive iteration state."""

    iteration.status = (
        "completed"
        if success
        else "failed"
    )

    if (
        adaptive_state.iteration_count
        >= adaptive_state.max_iterations
    ):
        adaptive_state.status = "budget_exhausted"
