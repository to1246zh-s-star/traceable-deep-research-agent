from models import (
    AdaptiveResearchState,
    ResearchAnalysis,
    ResearchGap,
)
from services.adaptive_research import (
    create_followup_tasks,
    plan_adaptive_iteration,
    record_iteration_finished,
    record_iteration_started,
    select_research_gaps,
)


def gap(
    gap_id,
    *,
    severity,
    query,
    status="open",
):
    return ResearchGap(
        gap_id=gap_id,
        candidate_id="cand_test",
        criterion_id="crit_test",
        gap_type="low_coverage",
        severity=severity,
        description=f"Gap {gap_id}",
        suggested_query=query,
        status=status,
    )


def test_selects_highest_severity_gaps():
    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            gap(
                "gap_low",
                severity=0.2,
                query="low query",
            ),
            gap(
                "gap_high",
                severity=0.9,
                query="high query",
            ),
        ],
    )

    state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    selected = select_research_gaps(
        analysis,
        state,
        max_tasks=1,
    )

    assert [
        item.gap_id
        for item in selected
    ] == ["gap_high"]


def test_duplicate_queries_are_not_replanned():
    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            gap(
                "gap_1",
                severity=0.9,
                query="Qdrant reliability benchmark",
            ),
            gap(
                "gap_2",
                severity=0.8,
                query=" qdrant   reliability benchmark ",
            ),
        ],
    )

    state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    selected = select_research_gaps(
        analysis,
        state,
    )

    assert len(selected) == 1
    assert selected[0].gap_id == "gap_1"


def test_previously_executed_gap_is_skipped():
    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            gap(
                "gap_done",
                severity=1.0,
                query="old query",
            ),
            gap(
                "gap_new",
                severity=0.8,
                query="new query",
            ),
        ],
    )

    state = AdaptiveResearchState(
        decision_id="dec_test",
        executed_gap_ids=["gap_done"],
    )

    selected = select_research_gaps(
        analysis,
        state,
    )

    assert [
        item.gap_id
        for item in selected
    ] == ["gap_new"]


def test_followup_tasks_receive_unique_sequential_ids():
    gaps = [
        gap(
            "gap_1",
            severity=1.0,
            query="query one",
        ),
        gap(
            "gap_2",
            severity=0.8,
            query="query two",
        ),
    ]

    tasks = create_followup_tasks(
        gaps,
        starting_task_id=5,
    )

    assert [
        task.id
        for task in tasks
    ] == [6, 7]

    assert tasks[0].query == "query one"
    assert tasks[1].query == "query two"


def test_plan_iteration_creates_tasks_and_iteration():
    gaps = [
        gap(
            "gap_1",
            severity=1.0,
            query="query one",
        )
    ]

    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=gaps,
    )

    state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    iteration, tasks = plan_adaptive_iteration(
        analysis,
        state,
        starting_task_id=2,
    )

    assert iteration is not None
    assert iteration.iteration_number == 1
    assert iteration.gap_ids == ["gap_1"]
    assert iteration.task_ids == [3]

    assert len(tasks) == 1
    assert tasks[0].id == 3


def test_iteration_recording_updates_adaptive_state():
    research_gap = gap(
        "gap_1",
        severity=1.0,
        query="query one",
    )

    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[research_gap],
    )

    state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    iteration, _ = plan_adaptive_iteration(
        analysis,
        state,
        starting_task_id=0,
    )

    assert iteration is not None

    record_iteration_started(
        state,
        iteration,
        [research_gap],
    )

    assert state.iteration_count == 1
    assert state.executed_gap_ids == [
        "gap_1"
    ]
    assert state.executed_queries == [
        "query one"
    ]
    assert iteration.status == "running"

    record_iteration_finished(
        state,
        iteration,
        success=True,
    )

    assert iteration.status == "completed"


def test_max_iterations_stops_replanning():
    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            gap(
                "gap_1",
                severity=1.0,
                query="query one",
            )
        ],
    )

    state = AdaptiveResearchState(
        decision_id="dec_test",
        iteration_count=2,
        max_iterations=2,
    )

    iteration, tasks = plan_adaptive_iteration(
        analysis,
        state,
        starting_task_id=0,
    )

    assert iteration is None
    assert tasks == []
    assert state.status == "budget_exhausted"


def test_no_actionable_gaps_stops_replanning():
    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[],
    )

    state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    iteration, tasks = plan_adaptive_iteration(
        analysis,
        state,
        starting_task_id=0,
    )

    assert iteration is None
    assert tasks == []
    assert state.status == "no_actionable_gaps"
