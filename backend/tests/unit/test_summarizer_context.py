from models import (
    SummaryState,
    TodoItem,
)

from services.context_engineering import (
    ContextAssembler,
)

from services.summarizer_context import (
    select_summarizer_context,
)


def _task() -> TodoItem:
    return TodoItem(
        id=1,
        title="Performance",
        intent="Compare performance",
        query="database benchmark",
    )


def test_summarizer_context_contains_topic():
    state = SummaryState(
        research_topic="Choose database"
    )

    result = ContextAssembler().assemble(
        select_summarizer_context(
            state,
            _task(),
            "Retrieved context",
        )
    )

    assert (
        "任务主题：Choose database"
        in result.rendered_text
    )


def test_summarizer_context_contains_task_metadata():
    state = SummaryState(
        research_topic="Topic"
    )

    result = ContextAssembler().assemble(
        select_summarizer_context(
            state,
            _task(),
            "Retrieved context",
        )
    )

    assert (
        "任务名称：Performance"
        in result.rendered_text
    )

    assert (
        "任务目标：Compare performance"
        in result.rendered_text
    )

    assert (
        "检索查询：database benchmark"
        in result.rendered_text
    )


def test_summarizer_context_contains_retrieved_context():
    state = SummaryState(
        research_topic="Topic"
    )

    result = ContextAssembler().assemble(
        select_summarizer_context(
            state,
            _task(),
            "Benchmark evidence",
        )
    )

    assert (
        "任务上下文："
        in result.rendered_text
    )

    assert (
        "Benchmark evidence"
        in result.rendered_text
    )


def test_empty_task_context_is_skipped():
    state = SummaryState(
        research_topic="Topic"
    )

    result = ContextAssembler().assemble(
        select_summarizer_context(
            state,
            _task(),
            "   ",
        )
    )

    assert (
        "Task Context"
        not in result.included_section_names
    )


def test_summarizer_context_does_not_mutate_inputs():
    state = SummaryState(
        research_topic="Topic"
    )

    task = _task()

    original_topic = (
        state.research_topic
    )

    original_title = (
        task.title
    )

    select_summarizer_context(
        state,
        task,
        "Context",
    )

    assert (
        state.research_topic
        == original_topic
    )

    assert (
        task.title
        == original_title
    )
