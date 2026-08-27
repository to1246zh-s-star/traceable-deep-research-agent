from threading import Lock

import agent as agent_module

from agent import DeepResearchAgent
from models import SummaryState, TodoItem


class FakeConfig:
    search_api = "tavily"
    fetch_full_page = False


class QuotaFailingSummarizer:
    def summarize_task(
        self,
        state,
        task,
        context,
    ):
        raise RuntimeError(
            "Error code: 429 - insufficient balance"
        )

    def is_valid_summary(self, value):
        return False


def test_quota_failure_opens_circuit_and_preserves_evidence(
    monkeypatch,
):
    research_agent = object.__new__(
        DeepResearchAgent
    )

    research_agent.config = FakeConfig()
    research_agent._state_lock = Lock()
    research_agent.summarizer = (
        QuotaFailingSummarizer()
    )
    research_agent._parallel_context_buffer = None
    research_agent._parallel_loop_counts = None
    research_agent._drain_tool_events = (
        lambda *args, **kwargs: []
    )

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [
                    {
                        "title": "Docs",
                        "url": "https://example.com",
                        "content": "evidence",
                    }
                ]
            },
            [],
            None,
            "tavily",
        ),
    )

    state = SummaryState(
        research_topic="A vs B",
    )

    task = TodoItem(
        id=1,
        title="Research",
        intent="Collect evidence",
        query="A docs",
    )

    state.todo_items = [task]

    list(
        research_agent._execute_task(
            state,
            task,
            emit_stream=False,
        )
    )

    assert task.status == "partial"
    assert len(state.evidence_items) == 1
    assert state.claims == []

    assert (
        state.llm_runtime_circuit["status"]
        == "open"
    )
    assert (
        state.llm_runtime_circuit["error_type"]
        == "quota_exceeded"
    )


def test_open_circuit_skips_later_task_summarizer(
    monkeypatch,
):
    research_agent = object.__new__(
        DeepResearchAgent
    )

    research_agent.config = FakeConfig()
    research_agent._state_lock = Lock()
    research_agent._parallel_context_buffer = None
    research_agent._parallel_loop_counts = None
    research_agent._drain_tool_events = (
        lambda *args, **kwargs: []
    )

    class MustNotRunSummarizer:
        def __init__(self):
            self.calls = 0

        def summarize_task(
            self,
            state,
            task,
            context,
        ):
            self.calls += 1
            raise AssertionError(
                "summarizer must be skipped"
            )

        def is_valid_summary(
            self,
            value,
        ):
            return False

    summarizer = MustNotRunSummarizer()
    research_agent.summarizer = summarizer

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [
                    {
                        "title": "Docs",
                        "url": "https://example.com",
                        "content": "evidence",
                    }
                ]
            },
            [],
            None,
            "tavily",
        ),
    )

    state = SummaryState(
        research_topic="A vs B",
        llm_runtime_circuit={
            "status": "open",
            "error_type": "quota_exceeded",
            "trigger_stage": "previous_task",
        },
    )

    task = TodoItem(
        id=2,
        title="Research B",
        intent="Collect evidence",
        query="B docs",
    )

    state.todo_items = [task]

    list(
        research_agent._execute_task(
            state,
            task,
            emit_stream=False,
        )
    )

    assert summarizer.calls == 0
    assert task.status == "partial"
    assert len(state.evidence_items) == 1
    assert state.claims == []

    assert (
        "summarization_skipped:"
        "llm_circuit_open"
        in task.notices
    )


def test_open_circuit_skips_later_task_summarizer(
    monkeypatch,
):
    research_agent = object.__new__(
        DeepResearchAgent
    )

    research_agent.config = FakeConfig()
    research_agent._state_lock = Lock()
    research_agent._parallel_context_buffer = None
    research_agent._parallel_loop_counts = None
    research_agent._drain_tool_events = (
        lambda *args, **kwargs: []
    )

    class MustNotRunSummarizer:
        def __init__(self):
            self.calls = 0

        def summarize_task(
            self,
            state,
            task,
            context,
        ):
            self.calls += 1
            raise AssertionError(
                "summarizer must be skipped"
            )

        def is_valid_summary(
            self,
            value,
        ):
            return False

    summarizer = MustNotRunSummarizer()
    research_agent.summarizer = summarizer

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [
                    {
                        "title": "Docs",
                        "url": "https://example.com",
                        "content": "evidence",
                    }
                ]
            },
            [],
            None,
            "tavily",
        ),
    )

    state = SummaryState(
        research_topic="A vs B",
        llm_runtime_circuit={
            "status": "open",
            "error_type": "quota_exceeded",
            "trigger_stage": "previous_task",
        },
    )

    task = TodoItem(
        id=2,
        title="Research B",
        intent="Collect evidence",
        query="B docs",
    )

    state.todo_items = [task]

    list(
        research_agent._execute_task(
            state,
            task,
            emit_stream=False,
        )
    )

    assert summarizer.calls == 0
    assert task.status == "partial"
    assert len(state.evidence_items) == 1
    assert state.claims == []

    assert (
        "summarization_skipped:"
        "llm_circuit_open"
        in task.notices
    )
