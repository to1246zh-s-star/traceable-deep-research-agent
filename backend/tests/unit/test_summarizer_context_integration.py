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
