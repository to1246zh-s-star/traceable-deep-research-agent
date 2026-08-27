import pytest

from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    DecisionCriterion,
    ReevaluationPlan,
    ResearchAnalysis,
    ResearchBudget,
    ResearchUsage,
)
from services.adaptive_research import (
    plan_adaptive_iteration,
)
from services.reevaluation_gap_bridge import (
    build_reevaluation_research_gaps,
)


def decision():
    return DecisionCase(
        decision_id="dec_test",
        question="Choose A or B",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            ),
            Candidate(
                candidate_id="cand_b",
                name="B",
            ),
        ],
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operational reliability",
                weight=1.0,
            ),
            DecisionCriterion(
                criterion_id="crit_scale",
                name="Scalability",
                weight=1.0,
            ),
        ],
    )


def plan(
    *,
    status="REQUIRED",
    queries=None,
    candidates=None,
    criteria=None,
):
    return ReevaluationPlan(
        decision_id="dec_test",
        status=status,
        matched_trigger_ids=[
            "trg_context",
        ],
        modules_to_recompute=[
            "integration_assessment",
            "scenario_analysis",
        ],
        candidate_ids_to_recheck=(
            ["cand_a"]
            if candidates is None
            else candidates
        ),
        criterion_ids_to_recheck=(
            ["crit_ops"]
            if criteria is None
            else criteria
        ),
        scenario_ids_to_recheck=[
            "scn_arch",
        ],
        research_queries=(
            [
                (
                    "A operational reliability "
                    "deployment environment updated evidence"
                )
            ]
            if queries is None
            else queries
        ),
        reasons=[
            "Deployment context changed."
        ],
    )


def test_required_plan_creates_open_gap():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )

    assert len(gaps) == 1

    gap = gaps[0]

    assert gap.gap_type == "reevaluation"
    assert gap.status == "open"
    assert gap.priority == 3
    assert gap.severity == 1.0

    assert gap.candidate_id == "cand_a"
    assert gap.criterion_id == "crit_ops"


def test_recommended_plan_uses_lower_routing_priority():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(
            status="RECOMMENDED"
        ),
    )

    assert len(gaps) == 1
    assert gaps[0].priority == 2
    assert gaps[0].severity == 0.7


def test_not_required_plan_creates_no_gaps():
    assert (
        build_reevaluation_research_gaps(
            decision(),
            plan(
                status="NOT_REQUIRED"
            ),
        )
        == []
    )


def test_unknown_plan_creates_no_gaps():
    assert (
        build_reevaluation_research_gaps(
            decision(),
            plan(
                status="UNKNOWN"
            ),
        )
        == []
    )


def test_empty_research_queries_create_no_gaps():
    assert (
        build_reevaluation_research_gaps(
            decision(),
            plan(
                queries=[],
            ),
        )
        == []
    )


def test_duplicate_queries_are_deduplicated():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(
            queries=[
                "A reliability updated evidence",
                "  a   reliability updated evidence  ",
            ]
        ),
    )

    assert len(gaps) == 1


def test_gap_id_is_deterministic():
    first = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )[0]

    second = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )[0]

    assert first.gap_id == second.gap_id


def test_multiple_candidates_do_not_create_fake_pairs():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(
            candidates=[
                "cand_a",
                "cand_b",
            ],
            criteria=[
                "crit_ops",
            ],
        ),
    )

    assert len(gaps) == 1

    # Aggregated scope is preserved without inventing
    # cand_a × crit_ops / cand_b × crit_ops linkage.
    assert gaps[0].candidate_id == ""
    assert gaps[0].criterion_id == "crit_ops"


def test_multiple_criteria_do_not_create_fake_pairs():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(
            candidates=[
                "cand_a",
            ],
            criteria=[
                "crit_ops",
                "crit_scale",
            ],
        ),
    )

    assert len(gaps) == 1

    assert gaps[0].candidate_id == "cand_a"
    assert gaps[0].criterion_id == ""


def test_unknown_scope_ids_are_not_propagated():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(
            candidates=[
                "not_real",
            ],
            criteria=[
                "not_real",
            ],
        ),
    )

    assert len(gaps) == 1

    assert gaps[0].candidate_id == ""
    assert gaps[0].criterion_id == ""


def test_search_strategy_is_assigned_by_existing_service():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )

    gap = gaps[0]

    assert gap.search_strategy
    assert gap.preferred_source_types
    assert gap.query_qualifiers

    assert gap.suggested_query


def test_bridge_does_not_create_tasks_or_decision_outputs():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )

    gap = gaps[0]

    assert not hasattr(
        gap,
        "candidate_scores",
    )

    assert not hasattr(
        gap,
        "predicted_winner_id",
    )

    assert not hasattr(
        gap,
        "recommendation",
    )

    assert not hasattr(
        gap,
        "tasks",
    )


def test_decision_id_mismatch_is_rejected():
    item = plan()
    item.decision_id = "dec_other"

    with pytest.raises(
        ValueError,
        match="decision_id",
    ):
        build_reevaluation_research_gaps(
            decision(),
            item,
        )


def test_existing_adaptive_planner_can_consume_bridge_gap():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )

    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=gaps,
    )

    adaptive_state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    iteration, tasks = plan_adaptive_iteration(
        analysis,
        adaptive_state,
        starting_task_id=10,
    )

    assert iteration is not None
    assert len(tasks) == 1

    assert iteration.gap_ids == [
        gaps[0].gap_id
    ]

    assert tasks[0].query


def test_existing_budget_still_blocks_reevaluation_gap():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )

    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=gaps,
    )

    adaptive_state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    budget = ResearchBudget(
        max_iterations=3,
        max_tasks=1,
    )

    usage = ResearchUsage(
        tasks=1,
    )

    iteration, tasks = plan_adaptive_iteration(
        analysis,
        adaptive_state,
        starting_task_id=0,
        research_budget=budget,
        research_usage=usage,
    )

    assert iteration is None
    assert tasks == []

    assert adaptive_state.status == (
        "budget_exhausted"
    )


def test_existing_query_dedupe_still_applies():
    gaps = build_reevaluation_research_gaps(
        decision(),
        plan(),
    )

    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=gaps,
    )

    adaptive_state = AdaptiveResearchState(
        decision_id="dec_test",
        executed_queries=[
            gaps[0].suggested_query
        ],
    )

    iteration, tasks = plan_adaptive_iteration(
        analysis,
        adaptive_state,
        starting_task_id=0,
    )

    assert iteration is None
    assert tasks == []


def test_plan_is_not_mutated():
    item = plan()

    before_queries = list(
        item.research_queries
    )
    before_modules = list(
        item.modules_to_recompute
    )

    build_reevaluation_research_gaps(
        decision(),
        item,
    )

    assert item.research_queries == (
        before_queries
    )

    assert item.modules_to_recompute == (
        before_modules
    )
