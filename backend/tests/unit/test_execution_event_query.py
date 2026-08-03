from threading import Lock

from agent import DeepResearchAgent
from models import SummaryState


def build_agent():
    agent = DeepResearchAgent.__new__(DeepResearchAgent)
    agent._state_lock = Lock()
    return agent


def test_query_execution_events_by_task():
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
        task_id=2,
        event_type="task_started",
        stage="executor",
    )

    events = agent.get_execution_events(
        state,
        task_id=1,
    )

    assert len(events) == 1
    assert events[0].task_id == 1


def test_query_execution_events_by_type():
    agent = build_agent()

    state = SummaryState(
        research_topic="test"
    )

    agent._emit_execution_event(
        state,
        task_id=1,
        event_type="task_failed",
        stage="executor",
    )

    agent._emit_execution_event(
        state,
        task_id=1,
        event_type="task_completed",
        stage="executor",
    )

    events = agent.get_execution_events(
        state,
        event_type="task_failed",
    )

    assert len(events) == 1
    assert events[0].event_type == "task_failed"


def test_query_execution_events_without_filter_returns_all():
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

    assert len(agent.get_execution_events(state)) == 1
