from threading import Lock
from types import SimpleNamespace

import agent as agent_module
from agent import DeepResearchAgent
from models import SummaryState, TodoItem


class DummyToolTracker:
    def drain(self, state, *, step=None):
        return []


def build_test_agent() -> DeepResearchAgent:
    """Create an agent without initialising a real LLM or external tools."""
    research_agent = DeepResearchAgent.__new__(DeepResearchAgent)
    research_agent.config = SimpleNamespace()
    research_agent._state_lock = Lock()
    research_agent._tool_tracker = DummyToolTracker()
    research_agent._tool_event_sink_enabled = False
    research_agent._last_search_notices = []
    return research_agent


def test_empty_search_result_records_skipped_execution_trace(monkeypatch) -> None:
    def fake_dispatch_search(query, config, loop_count):
        return (
            {
                "results": [],
                "backend": "fake",
                "answer": None,
                "notices": [],
            },
            [],
            None,
            "fake",
        )

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        fake_dispatch_search,
    )

    research_agent = build_test_agent()
    state = SummaryState(research_topic="Test topic")
    task = TodoItem(
        id=1,
        title="Test task",
        intent="Test executor trace",
        query="test query",
    )
    state.todo_items = [task]

    events = list(
        research_agent._execute_task(
            state,
            task,
            emit_stream=False,
        )
    )

    assert events == []
    assert task.status == "skipped"

    assert len(state.execution_traces) == 1

    trace = state.execution_traces[0]
    assert trace.task_id == task.id
    assert trace.status == "skipped"
    assert trace.current_stage == "search"
    assert trace.started_at is not None
    assert trace.finished_at is not None
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0
    assert trace.error_type is None
    assert trace.error_message is None
