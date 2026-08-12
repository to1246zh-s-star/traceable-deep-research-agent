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


def test_trace_contains_related_events():

    agent = build_agent()

    state = SummaryState(
        research_topic="test"
    )

    trace_id = "trace_test"

    trace = ExecutionTrace(
        trace_id=trace_id,
        task_id=1,
        status="completed",
    )

    state.execution_traces.append(trace)

    state.execution_event_history.extend(
        [
            ExecutionEvent(
                trace_id=trace_id,
                task_id=1,
                event_type="task_started",
                stage="executor",
            ),
            ExecutionEvent(
                trace_id=trace_id,
                task_id=1,
                event_type="task_completed",
                stage="executor",
            ),
        ]
    )

    result = agent.get_execution_trace(
        state,
        trace_id,
    )

    assert result["trace"].trace_id == trace_id
    assert len(result["events"]) == 2
