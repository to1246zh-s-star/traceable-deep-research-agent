from models import SummaryState, TodoItem
from tests.unit.test_executor_trace_lifecycle import (
    DummySummarizer,
    build_test_agent,
)


def test_completed_task_generates_execution_events(monkeypatch) -> None:
    def fake_dispatch_search(query, config, loop_count):
        return (
            {
                "results": [
                    {
                        "title": "Example source",
                        "url": "https://example.com",
                        "content": "Example evidence",
                    }
                ],
                "backend": "fake",
                "answer": None,
                "notices": [],
            },
            [],
            None,
            "fake",
        )

    monkeypatch.setattr(
        "agent.dispatch_search",
        fake_dispatch_search,
    )

    def fake_prepare_research_context(
        search_result,
        answer_text,
        config,
    ):
        return (
            "Example source summary",
            "Example research context",
        )

    monkeypatch.setattr(
        "agent.prepare_research_context",
        fake_prepare_research_context,
    )

    research_agent = build_test_agent()
    research_agent.summarizer = DummySummarizer()

    state = SummaryState(
        research_topic="Test topic"
    )

    task = TodoItem(
        id=1,
        title="Event task",
        intent="Test execution events",
        query="event query",
    )

    list(
        research_agent._execute_task(
            state,
            task,
            emit_stream=False,
        )
    )

    event_types = [
        event.event_type
        for event in state.execution_events
    ]

    assert "task_started" in event_types
    assert "search_started" in event_types
    assert "search_finished" in event_types
    assert "summarization_started" in event_types
    assert "task_completed" in event_types
