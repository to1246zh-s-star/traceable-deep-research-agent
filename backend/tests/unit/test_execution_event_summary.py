from threading import Lock

from agent import DeepResearchAgent
from models import SummaryState


def build_agent():
    agent = DeepResearchAgent.__new__(DeepResearchAgent)
    agent._state_lock = Lock()
    return agent


def test_execution_event_summary_counts_events():
    agent = build_agent()

    state = SummaryState(
        research_topic="test"
    )

    agent._emit_execution_event(
        state,
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    agent._emit_execution_event(
        state,
        task_id=1,
        event_type="task_completed",
        stage="executor",
    )

    agent._emit_execution_event(
        state,
        task_id=2,
        event_type="task_failed",
        stage="executor",
    )

    summary = agent.get_execution_event_summary(
        state
    )

    assert summary["total_events"] == 3
    assert summary["completed_tasks"] == 1
    assert summary["failed_tasks"] == 1
    assert summary["skipped_tasks"] == 0
    assert summary["event_counts"]["task_started"] == 1


def test_empty_execution_event_summary():
    agent = build_agent()

    state = SummaryState(
        research_topic="test"
    )

    summary = agent.get_execution_event_summary(
        state
    )

    assert summary["total_events"] == 0
    assert summary["event_counts"] == {}
