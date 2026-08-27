from agent import DeepResearchAgent
from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    ReevaluationAssessment,
    ReevaluationPlan,
    ReevaluationPreparation,
    ReevaluationReactivationDecision,
    ResearchAnalysis,
    ResearchGap,
    ResearchStoppingDecision,
    SummaryState,
)


def gap():
    return ResearchGap(
        gap_id="gap_new",
        candidate_id="",
        criterion_id="",
        gap_type="reevaluation",
        severity=1.0,
        description="New evidence",
        suggested_query="new evidence",
        priority=3,
    )


def state():
    return SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_test",
            question="A or B",
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
        ),
        research_analysis=ResearchAnalysis(
            decision_id="dec_test",
            status="complete",
        ),
        adaptive_research_state=AdaptiveResearchState(
            decision_id="dec_test",
            status="stopped",
        ),
        stopping_decision=ResearchStoppingDecision(
            should_continue=False,
            reason=(
                "insufficient_marginal_improvement"
            ),
            readiness_score=0.6,
            readiness_status="CONFLICTED",
        ),
    )


def preparation(*, eligible=True):
    item = gap()

    return ReevaluationPreparation(
        decision_id="dec_test",
        assessment=ReevaluationAssessment(
            decision_id="dec_test",
            status=(
                "REQUIRED"
                if eligible
                else "UNKNOWN"
            ),
        ),
        plan=ReevaluationPlan(
            decision_id="dec_test",
            status=(
                "REQUIRED"
                if eligible
                else "UNKNOWN"
            ),
        ),
        reevaluation_gaps=(
            [item]
            if eligible
            else []
        ),
        merged_analysis=ResearchAnalysis(
            decision_id="dec_test",
            research_gaps=(
                [item]
                if eligible
                else []
            ),
            status=(
                "gaps_detected"
                if eligible
                else "complete"
            ),
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
                    ["gap_new"]
                    if eligible
                    else []
                ),
            )
        ),
    )


def test_blocked_preparation_does_not_run_loop(
    monkeypatch,
):
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    called = []

    def fake_loop(
        state_arg,
        *,
        max_tasks_per_iteration,
    ):
        called.append(
            max_tasks_per_iteration
        )
        return state_arg

    monkeypatch.setattr(
        agent,
        "execute_adaptive_decision_loop",
        fake_loop,
    )

    item = state()

    result = agent.execute_prepared_reevaluation(
        item,
        preparation(
            eligible=False,
        ),
    )

    assert result is item
    assert called == []


def test_eligible_preparation_runs_existing_loop(
    monkeypatch,
):
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    item = state()

    called = []

    def fake_loop(
        state_arg,
        *,
        max_tasks_per_iteration,
    ):
        called.append(
            max_tasks_per_iteration
        )
        return state_arg

    monkeypatch.setattr(
        agent,
        "execute_adaptive_decision_loop",
        fake_loop,
    )

    result = agent.execute_prepared_reevaluation(
        item,
        preparation(),
        max_tasks_per_iteration=2,
    )

    assert result is item

    assert called == [
        2,
    ]

    assert (
        item.adaptive_research_state.status
        == "active"
    )

    assert (
        item.stopping_decision.should_continue
        is True
    )

    assert [
        gap.gap_id
        for gap
        in item.research_analysis.research_gaps
    ] == [
        "gap_new",
    ]
