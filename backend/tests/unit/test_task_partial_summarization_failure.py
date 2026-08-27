from threading import Lock

import agent as agent_module

from agent import DeepResearchAgent
from models import SummaryState, TodoItem


class FakeConfig:
    search_api = "tavily"
    fetch_full_page = False


class FailingSummarizer:
    def summarize_task(
        self,
        state,
        task,
        context,
    ):
        raise RuntimeError(
            "Error code: 429 - rate limit"
        )

    def is_valid_summary(self, value):
        return bool(value)


def test_summary_failure_preserves_retrieval_as_partial(
    monkeypatch,
):
    research_agent = object.__new__(
        DeepResearchAgent
    )

    research_agent.config = FakeConfig()
    research_agent._state_lock = Lock()
    research_agent.summarizer = (
        FailingSummarizer()
    )

    research_agent._parallel_context_buffer = None
    research_agent._parallel_loop_counts = None

    research_agent._drain_tool_events = (
        lambda *args, **kwargs: []
    )

    def fake_dispatch_search(
        query,
        config,
        loop_count,
    ):
        return (
            {
                "results": [
                    {
                        "title": "Official docs",
                        "url": (
                            "https://example.com/docs"
                        ),
                        "content": (
                            "Retrieved evidence content"
                        ),
                    }
                ]
            },
            [],
            None,
            "tavily",
        )

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        fake_dispatch_search,
    )

    state = SummaryState(
        research_topic="A vs B",
    )

    task = TodoItem(
        id=1,
        title="Research A",
        intent="Collect evidence",
        query="A official docs",
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

    assert task.status == "partial"

    assert (
        "summarization_failed:rate_limited"
        in task.notices
    )

    assert task.sources_summary
    assert len(state.evidence_items) == 1

    # Failed summarization must not create a fake claim.
    assert state.claims == []

    assert len(state.execution_traces) == 1

    trace = state.execution_traces[0]

    assert trace.status == "partial"
    assert trace.error_type == "rate_limited"

    partial_events = [
        event
        for event in state.execution_events
        if event.event_type == "task_partial"
    ]

    assert len(partial_events) == 1

    assert (
        partial_events[0].metadata[
            "evidence_preserved"
        ]
        == 1
    )
