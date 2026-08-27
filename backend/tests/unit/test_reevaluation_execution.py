import pytest

from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    ReevaluationAssessment,
    ReevaluationPlan,
    ReevaluationPreparation,
    ReevaluationReactivationDecision,
    ResearchAnalysis,
    ResearchBudget,
    ResearchGap,
    ResearchStoppingDecision,
    ResearchUsage,
    SummaryState,
)
from services.reevaluation_execution import (
    activate_prepared_reevaluation,
)


def old_gap():
    return ResearchGap(
        gap_id="gap_old",
        candidate_id="cand_a",
        criterion_id="crit_a",
        gap_type="low_coverage",
        severity=0.5,
        description="Old gap",
        suggested_query="old query",
    )


def new_gap():
    return ResearchGap(
        gap_id="gap_new",
        candidate_id="",
        criterion_id="",
        gap_type="reevaluation",
        severity=1.0,
        description="Reevaluate new evidence",
        suggested_query="new evidence query",
        priority=3,
    )


def state():
    decision = DecisionCase(
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
    )

    return SummaryState(
        research_topic="A vs B",
        decision_case=decision,
        research_analysis=ResearchAnalysis(
            decision_id="dec_test",
            research_gaps=[
                old_gap(),
            ],
            status="gaps_detected",
        ),
        adaptive_research_state=(
            AdaptiveResearchState(
                decision_id="dec_test",
                iteration_count=1,
                max_iterations=3,
                executed_gap_ids=[
                    "gap_old",
                ],
                executed_queries=[
                    "old query",
                ],
                status="stopped",
            )
        ),
        research_budget=ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        research_usage=ResearchUsage(
            iterations=1,
            tasks=3,
        ),
        stopping_decision=(
            ResearchStoppingDecision(
                should_continue=False,
                reason=(
                    "insufficient_marginal_improvement"
                ),
                readiness_score=0.6,
                readiness_status="CONFLICTED",
                actionable_gap_count=1,
                blocking_budget_limits=[],
            )
        ),
    )


def preparation(
    *,
    eligible=True,
):
    gap = new_gap()

    return ReevaluationPreparation(
        decision_id="dec_test",
        assessment=ReevaluationAssessment(
            decision_id="dec_test",
            status=(
                "REQUIRED"
                if eligible
                else "NOT_REQUIRED"
            ),
        ),
        plan=ReevaluationPlan(
            decision_id="dec_test",
            status=(
                "REQUIRED"
                if eligible
                else "NOT_REQUIRED"
            ),
        ),
        reevaluation_gaps=(
            [gap]
            if eligible
            else []
        ),
        merged_analysis=ResearchAnalysis(
            decision_id="dec_test",
            research_gaps=(
                [
                    old_gap(),
                    gap,
                ]
                if eligible
                else [
                    old_gap(),
                ]
            ),
            status="gaps_detected",
        ),
        reactivation=(
            ReevaluationReactivationDecision(
                decision_id="dec_test",
                status=(
                    "ELIGIBLE"
                    if eligible
                    else "BLOCKED"
                ),
                eligible=eligible,
                actionable_gap_ids=(
                    [
                        "gap_new",
                    ]
                    if eligible
                    else []
                ),
            )
        ),
    )


def test_eligible_preparation_installs_merged_analysis():
    item = state()
    prepared = preparation()

    result = activate_prepared_reevaluation(
        item,
        prepared,
    )

    assert result is item

    assert (
        result.research_analysis
        is prepared.merged_analysis
    )

    assert [
        gap.gap_id
        for gap
        in result.research_analysis.research_gaps
    ] == [
        "gap_old",
        "gap_new",
    ]


def test_eligible_preparation_reopens_lifecycle():
    item = state()

    activate_prepared_reevaluation(
        item,
        preparation(),
    )

    assert (
        item.adaptive_research_state.status
        == "active"
    )

    assert (
        item.stopping_decision.should_continue
        is True
    )

    assert (
        item.stopping_decision.reason
        == "continue_research"
    )


def test_activation_preserves_budget_and_usage_objects():
    item = state()

    budget = item.research_budget
    usage = item.research_usage

    activate_prepared_reevaluation(
        item,
        preparation(),
    )

    assert item.research_budget is budget
    assert item.research_usage is usage

    assert item.research_usage.iterations == 1
    assert item.research_usage.tasks == 3


def test_activation_preserves_adaptive_history():
    item = state()

    adaptive = item.adaptive_research_state

    before_iteration_count = (
        adaptive.iteration_count
    )

    before_gap_ids = list(
        adaptive.executed_gap_ids
    )

    before_queries = list(
        adaptive.executed_queries
    )

    activate_prepared_reevaluation(
        item,
        preparation(),
    )

    assert (
        adaptive.iteration_count
        == before_iteration_count
    )

    assert (
        adaptive.executed_gap_ids
        == before_gap_ids
    )

    assert (
        adaptive.executed_queries
        == before_queries
    )


def test_blocked_preparation_is_complete_noop():
    item = state()

    old_analysis = item.research_analysis
    old_adaptive = item.adaptive_research_state
    old_stop = item.stopping_decision

    result = activate_prepared_reevaluation(
        item,
        preparation(
            eligible=False,
        ),
    )

    assert result is item

    assert item.research_analysis is old_analysis
    assert (
        item.adaptive_research_state
        is old_adaptive
    )

    assert item.stopping_decision is old_stop

    assert (
        item.adaptive_research_state.status
        == "stopped"
    )


def test_missing_decision_case_is_rejected():
    item = state()
    item.decision_case = None

    with pytest.raises(
        ValueError,
        match="without decision case",
    ):
        activate_prepared_reevaluation(
            item,
            preparation(),
        )


def test_preparation_decision_mismatch_is_rejected():
    prepared = preparation()
    prepared.decision_id = "dec_other"

    with pytest.raises(
        ValueError,
        match="preparation decision_id",
    ):
        activate_prepared_reevaluation(
            state(),
            prepared,
        )


def test_prepared_analysis_mismatch_is_rejected():
    prepared = preparation()

    prepared.merged_analysis.decision_id = (
        "dec_other"
    )

    with pytest.raises(
        ValueError,
        match="prepared analysis decision_id",
    ):
        activate_prepared_reevaluation(
            state(),
            prepared,
        )


def test_missing_adaptive_state_is_rejected():
    item = state()
    item.adaptive_research_state = None

    with pytest.raises(
        ValueError,
        match="without adaptive research state",
    ):
        activate_prepared_reevaluation(
            item,
            preparation(),
        )


def test_activation_does_not_create_decision_outputs():
    item = state()

    activate_prepared_reevaluation(
        item,
        preparation(),
    )

    assert not hasattr(
        item.adaptive_research_state,
        "candidate_scores",
    )

    assert not hasattr(
        item.adaptive_research_state,
        "recommendation",
    )

    assert not hasattr(
        item.adaptive_research_state,
        "predicted_winner_id",
    )
