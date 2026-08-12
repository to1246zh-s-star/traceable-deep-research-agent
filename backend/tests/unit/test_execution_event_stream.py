from threading import Lock
from types import SimpleNamespace

import agent as agent_module
from agent import DeepResearchAgent
from models import SummaryState, TodoItem


class DummyToolTracker:
    def drain(self, state, *, step=None):
        return []


class DummySummarizer:
    def summarize_task(self, state, task, context):
        return "Valid summary."

    def stream_task_summary(self, state, task, context):
        def stream():
            yield "Valid summary."

        return stream(), lambda: "Valid summary."

    def is_valid_summary(self, summary):
        return True


def build_test_agent():
    research_agent = DeepResearchAgent.__new__(DeepResearchAgent)
    research_agent.config = SimpleNamespace()
    research_agent._state_lock = Lock()
    research_agent._tool_tracker = DummyToolTracker()
    research_agent._tool_event_sink_enabled = False
    research_agent._last_search_notices = []
    research_agent.summarizer = DummySummarizer()
    return research_agent


def test_execution_events_are_streamed(monkeypatch):
    def fake_dispatch_search(query, config, loop_count):
        return (
            {
                "results": [
                    {
                        "title": "source",
                        "url": "https://example.com",
                        "content": "content",
                    }
                ],
                "backend": "fake",
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

    monkeypatch.setattr(
        agent_module,
        "prepare_research_context",
        lambda *args: (
            "summary",
            "context",
        ),
    )

    agent = build_test_agent()

    state = SummaryState(
        research_topic="test"
    )

    task = TodoItem(
        id=1,
        title="stream event",
        intent="test stream",
        query="query",
    )

    events = list(
        agent._execute_task(
            state,
            task,
            emit_stream=True,
        )
    )

    assert any(
        event.get("type") == "execution_event"
        for event in events
    )
