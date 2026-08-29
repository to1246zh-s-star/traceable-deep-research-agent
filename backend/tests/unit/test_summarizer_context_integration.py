from models import (
    SummaryState,
    TodoItem,
)

from services.summarizer import (
    SummarizationService,
)


class RecordingAgent:
    def __init__(self):
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)

        return (
            "A sufficiently long Markdown summary "
            * 10
        )

    def clear_history(self):
        pass


class Config:
    strip_thinking_tokens = False


def _task() -> TodoItem:
    return TodoItem(
        id=1,
        title="Attention",
        intent="Explain attention",
        query="transformer attention",
    )


def test_summarizer_uses_assembled_context():
    agent = RecordingAgent()

    service = SummarizationService(
        lambda: agent,
        Config(),
    )

    state = SummaryState(
        research_topic="Transformers"
    )

    service.summarize_task(
        state,
        _task(),
        "Retrieved evidence",
    )

    prompt = agent.prompts[0]

    assert (
        "## Research Topic"
        in prompt
    )

    assert (
        "任务主题：Transformers"
        in prompt
    )

    assert (
        "## Task"
        in prompt
    )

    assert (
        "任务名称：Attention"
        in prompt
    )

    assert (
        "任务上下文："
        in prompt
    )

    assert (
        "Retrieved evidence"
        in prompt
    )

    assert (
        "SUMMARIZATION INSTRUCTION:"
        in prompt
    )


def test_summarizer_preserves_legacy_labels():
    agent = RecordingAgent()

    service = SummarizationService(
        lambda: agent,
        Config(),
    )

    state = SummaryState(
        research_topic="Transformers"
    )

    service.summarize_task(
        state,
        _task(),
        "Context",
    )

    prompt = agent.prompts[0]

    assert (
        "任务主题：Transformers"
        in prompt
    )

    assert (
        "任务名称：Attention"
        in prompt
    )

    assert (
        "任务目标：Explain attention"
        in prompt
    )

    assert (
        "检索查询：transformer attention"
        in prompt
    )

    assert (
        "任务上下文："
        in prompt
    )


def test_summarizer_budget_keeps_critical_task_context_metadata():
    agent = RecordingAgent()

    service = SummarizationService(
        lambda: agent,
        Config(),
    )

    state = SummaryState(
        research_topic="Large context research"
    )

    very_large_context = (
        "retrieved-content-" * 5000
    )

    service.summarize_task(
        state,
        _task(),
        very_large_context,
    )

    prompt = agent.prompts[0]

    assert (
        "任务主题：Large context research"
        in prompt
    )

    assert (
        "任务名称：Attention"
        in prompt
    )

    assert (
        very_large_context
        not in prompt
    )

    assert "retrieved-content-" in prompt
    assert "[... context compressed for execution ...]" in prompt
    assert state.context_compression_traces
    trace = state.context_compression_traces[-1]
    assert trace.section_name == "Task Context"
    assert trace.original_estimated_size > trace.compressed_estimated_size
    assert trace.reason == "section_exceeds_remaining_budget"

    budget_trace = state.context_budget_traces[-1]
    decisions = {item.section_name: item for item in budget_trace.decisions}
    task_context_decision = decisions["Task Context"]
    higher_priority_units = (
        decisions["Research Topic"].estimated_units
        + decisions["Task"].estimated_units
    )
    assert task_context_decision.estimated_units <= (
        budget_trace.available_units - higher_priority_units
    )
    assert task_context_decision.included is True


def test_summarizer_budget_keeps_normal_context_when_it_fits():
    agent = RecordingAgent()

    service = SummarizationService(
        lambda: agent,
        Config(),
    )

    state = SummaryState(
        research_topic="Normal context"
    )

    context = (
        "Short retrieved evidence"
    )

    service.summarize_task(
        state,
        _task(),
        context,
    )

    prompt = agent.prompts[0]

    assert context in prompt


def test_summarizer_records_budget_trace():
    agent = RecordingAgent()

    service = SummarizationService(
        lambda: agent,
        Config(),
    )

    state = SummaryState(
        research_topic="Budget trace"
    )

    large_context = (
        "large-context-" * 5000
    )

    service.summarize_task(
        state,
        _task(),
        large_context,
    )

    assert (
        state.context_budget_traces
    )

    trace = (
        state.context_budget_traces[-1]
    )

    assert (
        trace.purpose
        == "task_summary"
    )

    decisions = {
        item.section_name: item
        for item in trace.decisions
    }

    assert decisions["Task Context"].included is True

    assert (
        decisions["Task Context"]
        .reason
        == "within_budget"
    )
