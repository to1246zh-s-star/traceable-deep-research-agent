import agent as agent_module

from agent import DeepResearchAgent
from models import (
    AdaptiveResearchState,
    ResearchAnalysis,
    ResearchBudget,
    ResearchUsage,
    SummaryState,
)


def test_agent_forwards_persistent_budget_and_usage(
    monkeypatch,
):
    research_budget = ResearchBudget(
        max_iterations=3,
        max_tasks=4,
    )

    research_usage = ResearchUsage(
        iterations=1,
        tasks=3,
    )

    state = SummaryState(
        research_budget=research_budget,
        research_usage=research_usage,
    )

    analysis = ResearchAnalysis(
        decision_id="dec_test",
    )

    adaptive_state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    captured = {}

    def fake_plan(
        analysis_arg,
        adaptive_state_arg,
        *,
        starting_task_id,
        max_tasks,
        research_budget,
        research_usage,
    ):
        captured["budget"] = research_budget
        captured["usage"] = research_usage
        captured["max_tasks"] = max_tasks

        return None, []

    monkeypatch.setattr(
        agent_module,
        "plan_adaptive_iteration",
        fake_plan,
    )

    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    result = (
        DeepResearchAgent.execute_adaptive_followups(
            agent,
            state,
            analysis,
            adaptive_state,
            max_tasks=3,
        )
    )

    assert result is None

    assert (
        captured["budget"]
        is research_budget
    )

    assert (
        captured["usage"]
        is research_usage
    )

    assert captured["max_tasks"] == 3
