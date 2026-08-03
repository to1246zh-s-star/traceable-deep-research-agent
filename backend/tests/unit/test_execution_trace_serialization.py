from threading import Lock

from agent import DeepResearchAgent
from models import (
    SummaryState,
    ExecutionTrace,
    ExecutionEvent,
)


def build_agent():
    agent = DeepResearchAgent.__new__(DeepResearchAgent)
    agent._state_lock = Lock()
    return agent


def test_execution_trace_serialization():

    agent = build_agent()

    state = SummaryState(
        research_topic="test"
    )

    trace_id = "trace_test"

    state.execution_traces.append(
        ExecutionTrace(
            trace_id=trace_id,
            task_id=1,
            status="completed",
        )
    )

    state.execution_event_history.append(
        ExecutionEvent(
            trace_id=trace_id,
            task_id=1,
            event_type="task_completed",
            stage="executor",
        )
    )

    result = agent.serialize_execution_trace(
        state,
        trace_id,
    )

    assert result["trace"]["trace_id"] == trace_id
    assert result["events"][0]["event_type"] == "task_completed"
    assert "timestamp" in result["events"][0]
