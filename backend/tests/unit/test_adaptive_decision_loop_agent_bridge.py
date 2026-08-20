from agent import DeepResearchAgent
from models import (
    AdaptiveResearchIteration,
    DecisionCase,
    ResearchAnalysis,
    ResearchGap,
    ResearchStoppingDecision,
    SummaryState,
)


def continue_decision():
    return ResearchStoppingDecision(
        should_continue=True,
        reason="research_needed",
        readiness_score=0.4,
        readiness_status="NOT_READY",
        readiness_improvement=None,
        actionable_gap_count=1,
        blocking_budget_limits=[],
    )


def stop_decision():
    return ResearchStoppingDecision(
        should_continue=False,
        reason="decision_ready",
        readiness_score=0.8,
        readiness_status="READY",
        readiness_improvement=0.4,
        actionable_gap_count=0,
        blocking_budget_limits=[],
    )


def test_agent_bridge_runs_followup_and_recalculates_decision():
    agent = object.__new__(DeepResearchAgent)

    decision = DecisionCase(
        decision_id="dec_agent_loop",
        question="Choose A or B",
    )

    state = SummaryState(
        research_topic="A vs B",
        decision_case=decision,
        research_analysis=ResearchAnalysis(
            decision_id="dec_agent_loop",
            research_gaps=[
                ResearchGap(
                    gap_id="gap_1",
                    candidate_id="cand_a",
                    criterion_id="crit_1",
                    gap_type="low_coverage",
                    severity=0.8,
                    description="Need more evidence",
                    suggested_query="candidate A benchmark",
                )
            ],
        ),
        stopping_decision=continue_decision(),
    )

    calls = []

    def execute_followups(
        state,
        analysis,
        adaptive_state,
        *,
        max_tasks=3,
    ):
        calls.append("followup")

        return AdaptiveResearchIteration(
            decision_id="dec_agent_loop",
            iteration_number=1,
            gap_ids=["gap_1"],
            task_ids=[10, 11],
            status="completed",
        )

    def execute_intelligence(
        state,
        *,
        constraint_results=None,
        research_budget=None,
        research_usage=None,
    ):
        calls.append("decision")

        assert research_usage is not None
        assert research_usage.iterations == 1
        assert research_usage.tasks == 2

        state.stopping_decision = stop_decision()

        return state

    agent.execute_adaptive_followups = execute_followups
    agent.execute_decision_intelligence = execute_intelligence

    result = agent.execute_adaptive_decision_loop(
        state
    )

    assert result is state

    assert calls == [
        "followup",
        "decision",
    ]

    assert state.research_usage is not None
    assert state.research_usage.iterations == 1
    assert state.research_usage.tasks == 2

    assert state.adaptive_research_state is not None
    assert (
        state.adaptive_research_state.decision_id
        == "dec_agent_loop"
    )


def test_agent_bridge_non_decision_is_noop():
    agent = object.__new__(DeepResearchAgent)

    state = SummaryState(
        research_topic="Explain transformers",
    )

    agent.execute_adaptive_followups = (
        lambda *args, **kwargs: (
            (_ for _ in ()).throw(
                AssertionError(
                    "followups must not run"
                )
            )
        )
    )

    agent.execute_decision_intelligence = (
        lambda *args, **kwargs: (
            (_ for _ in ()).throw(
                AssertionError(
                    "decision intelligence must not run"
                )
            )
        )
    )

    result = agent.execute_adaptive_decision_loop(
        state
    )

    assert result is state
    assert state.research_usage is None
    assert state.adaptive_research_state is None
