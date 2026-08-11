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


class DummySummarizer:
    def summarize_task(self, state, task, context):
        return "Valid summary content."

    def is_valid_summary(self, summary):
        return bool(summary and summary.strip())


def test_successful_task_records_completed_execution_trace(monkeypatch) -> None:
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

    def fake_prepare_research_context(search_result, answer_text, config):
        return (
            "Example source summary",
            "Example research context",
        )

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        fake_dispatch_search,
    )
    monkeypatch.setattr(
        agent_module,
        "prepare_research_context",
        fake_prepare_research_context,
    )

    research_agent = build_test_agent()
    research_agent.summarizer = DummySummarizer()

    state = SummaryState(research_topic="Test topic")
    task = TodoItem(
        id=2,
        title="Successful task",
        intent="Test completed executor trace",
        query="successful query",
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
    assert task.status == "completed"
    assert task.summary == "Valid summary content."

    assert len(state.execution_traces) == 1

    trace = state.execution_traces[0]
    assert trace.task_id == task.id
    assert trace.status == "completed"
    assert trace.current_stage == "summarization"
    assert trace.started_at is not None
    assert trace.finished_at is not None
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0
    assert trace.error_type is None
    assert trace.error_message is None


def test_search_exception_records_failed_execution_trace(monkeypatch) -> None:
    def fake_dispatch_search(query, config, loop_count):
        raise TimeoutError("search timed out")

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        fake_dispatch_search,
    )

    research_agent = build_test_agent()
    state = SummaryState(research_topic="Test topic")
    task = TodoItem(
        id=3,
        title="Failed search task",
        intent="Test failed executor trace",
        query="failing query",
    )
    state.todo_items = [task]

    try:
        list(
            research_agent._execute_task(
                state,
                task,
                emit_stream=False,
            )
        )
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected TimeoutError to be raised")

    assert task.status == "failed"
    assert len(state.execution_traces) == 1

    trace = state.execution_traces[0]
    assert trace.task_id == task.id
    assert trace.status == "failed"
    assert trace.current_stage == "search"
    assert trace.started_at is not None
    assert trace.finished_at is not None
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0
    assert trace.error_type == "timeout"
    assert trace.error_message == "search timed out"


class FailingSummarizer:
    def summarize_task(self, state, task, context):
        raise RuntimeError("summary generation failed")

    def is_valid_summary(self, summary):
        return False


def test_summarization_exception_records_failed_execution_trace(monkeypatch) -> None:
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

    def fake_prepare_research_context(search_result, answer_text, config):
        return (
            "Example source summary",
            "Example research context",
        )

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        fake_dispatch_search,
    )
    monkeypatch.setattr(
        agent_module,
        "prepare_research_context",
        fake_prepare_research_context,
    )

    research_agent = build_test_agent()
    research_agent.summarizer = FailingSummarizer()

    state = SummaryState(research_topic="Test topic")
    task = TodoItem(
        id=4,
        title="Failed summary task",
        intent="Test summarization failure trace",
        query="successful search query",
    )
    state.todo_items = [task]

    try:
        list(
            research_agent._execute_task(
                state,
                task,
                emit_stream=False,
            )
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError to be raised")

    assert task.status == "failed"
    assert len(state.execution_traces) == 1

    trace = state.execution_traces[0]
    assert trace.task_id == task.id
    assert trace.status == "failed"
    assert trace.current_stage == "summarization"
    assert trace.started_at is not None
    assert trace.finished_at is not None
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0
    assert trace.error_type == "provider_error"
    assert trace.error_message == "summary generation failed"


def test_successful_task_records_traceable_evidence(monkeypatch) -> None:
    def fake_dispatch_search(query, config, loop_count):
        return (
            {
                "results": [
                    {
                        "title": "Evidence source",
                        "url": "https://example.com/evidence",
                        "content": "Search result evidence snippet.",
                        "raw_content": "Full evidence page content.",
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

    def fake_prepare_research_context(search_result, answer_text, config):
        return (
            "Evidence source summary",
            "Evidence research context",
        )

    monkeypatch.setattr(
        agent_module,
        "dispatch_search",
        fake_dispatch_search,
    )
    monkeypatch.setattr(
        agent_module,
        "prepare_research_context",
        fake_prepare_research_context,
    )

    research_agent = build_test_agent()
    research_agent.summarizer = DummySummarizer()

    state = SummaryState(research_topic="Evidence integration")
    task = TodoItem(
        id=5,
        title="Evidence task",
        intent="Verify traceable evidence",
        query="traceable evidence query",
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
    assert task.status == "completed"

    assert len(state.execution_traces) == 1
    assert len(state.evidence_items) == 1

    trace = state.execution_traces[0]
    evidence = state.evidence_items[0]

    assert evidence.task_id == task.id
    assert evidence.trace_id == trace.trace_id

    assert evidence.query == task.query
    assert evidence.backend == "fake"

    assert evidence.source_title == "Evidence source"
    assert evidence.source_url == "https://example.com/evidence"
    assert evidence.snippet == "Search result evidence snippet."
    assert evidence.content == "Full evidence page content."
    assert evidence.source_rank == 1
