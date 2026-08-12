from threading import Lock

from agent import DeepResearchAgent
from models import SummaryState


def test_execution_event_history_preserves_events():
    agent = DeepResearchAgent.__new__(DeepResearchAgent)
    agent._state_lock = Lock()

    state = SummaryState(
        research_topic="test"
    )

    agent._emit_execution_event(
        state,
        task_id=1,
        event_type="task_started",
        stage="executor",
    )

    assert len(state.execution_events) == 1
    assert len(state.execution_event_history) == 1

    drained = agent._drain_execution_events(state)

    assert len(drained) == 1

    # stream queue cleared
    assert state.execution_events == []

    # history remains
    assert len(state.execution_event_history) == 1
    assert state.execution_event_history[0].event_type == "task_started"
