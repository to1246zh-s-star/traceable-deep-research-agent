import pytest

from models import SummaryState, TodoItem
from test_executor_trace_lifecycle import build_test_agent



def test_search_failure_generates_failed_event(monkeypatch):
    def fake_dispatch_search(query, config, loop_count):
        raise TimeoutError("search timeout")

    monkeypatch.setattr(
        "agent.dispatch_search",
        fake_dispatch_search,
    )

    agent = build_test_agent()

    state = SummaryState(
        research_topic="test"
    )

    task = TodoItem(
        id=1,
        title="failed search",
        intent="test",
        query="timeout",
    )

    with pytest.raises(TimeoutError):
        list(
            agent._execute_task(
                state,
                task,
                emit_stream=False,
            )
        )

    event_types = [
        e.event_type
        for e in state.execution_events
    ]

    assert "task_failed" in event_types


def test_empty_search_generates_skipped_event(monkeypatch):
    def fake_dispatch_search(query, config, loop_count):
        return (
            {
                "results": [],
                "backend": "fake",
            },
            [],
            None,
            "fake",
        )

    monkeypatch.setattr(
        "agent.dispatch_search",
        fake_dispatch_search,
    )

    agent = build_test_agent()

    state = SummaryState(
        research_topic="test"
    )

    task = TodoItem(
        id=2,
        title="empty",
        intent="test",
        query="empty",
    )

    list(
        agent._execute_task(
            state,
            task,
            emit_stream=False,
        )
    )

    event_types = [
        e.event_type
        for e in state.execution_events
    ]

    assert "task_skipped" in event_types


def test_summary_failure_generates_failed_event(monkeypatch):
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

    def fake_prepare_research_context(
        search_result,
        answer_text,
        config,
    ):
        return (
            "summary",
            "context",
        )

    monkeypatch.setattr(
        "agent.dispatch_search",
        fake_dispatch_search,
    )

    monkeypatch.setattr(
        "agent.prepare_research_context",
        fake_prepare_research_context,
    )

    agent = build_test_agent()

    class FailingSummarizer:
        def summarize_task(self, state, task, context):
            raise RuntimeError(
                "summary failed"
            )

        def is_valid_summary(self, summary):
            return False

    agent.summarizer = FailingSummarizer()

    state = SummaryState(
        research_topic="test"
    )

    task = TodoItem(
        id=3,
        title="summary",
        intent="test",
        query="summary",
    )

    with pytest.raises(RuntimeError):
        list(
            agent._execute_task(
                state,
                task,
                emit_stream=False,
            )
        )

    event_types = [
        e.event_type
        for e in state.execution_events
    ]

    assert "task_failed" in event_types


def test_degraded_empty_search_is_skipped_not_failed(
    monkeypatch,
):
    from agent import DeepResearchAgent
    from config import Configuration
    from models import SummaryState, TodoItem

    research_agent = DeepResearchAgent(
        Configuration(
            enable_notes=False,
        )
    )

    def fake_dispatch_search(
        query,
        config,
        loop_count,
    ):
        return (
            {
                "results": [],
                "backend": "tavily",
                "answer": None,
                "notices": [
                    "provider degraded"
                ],
                "degraded": True,
                "error_type": "TimeoutError",
            },
            [
                "provider degraded"
            ],
            None,
            "tavily",
        )

    monkeypatch.setattr(
        "agent.dispatch_search",
        fake_dispatch_search,
    )

    state = SummaryState(
        research_topic="A vs B"
    )

    task = TodoItem(
        id=1,
        title="Search",
        intent="Find evidence",
        query="A benchmark",
    )

    list(
        research_agent._execute_task(
            state,
            task,
            emit_stream=False,
        )
    )

    assert task.status == "skipped"
    assert task.notices == [
        "provider degraded"
    ]

    assert len(
        state.execution_traces
    ) == 1

    trace = state.execution_traces[0]

    assert trace.status == "skipped"
    assert trace.error_type is None
    assert trace.error_message is None
