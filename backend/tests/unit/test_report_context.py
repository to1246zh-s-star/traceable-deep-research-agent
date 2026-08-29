from models import (
    SummaryState,
    TodoItem,
)

from services.context_engineering import (
    ContextAssembler,
)

from services.report_context import (
    select_report_context,
)


def test_report_context_contains_topic():
    state = SummaryState(
        research_topic="Choose database"
    )

    selection = select_report_context(
        state
    )

    result = ContextAssembler().assemble(
        selection
    )

    assert (
        "Choose database"
        in result.rendered_text
    )


def test_report_context_contains_task_results():
    state = SummaryState(
        research_topic="Topic",
        todo_items=[
            TodoItem(
                id=1,
                title="Performance",
                intent="Compare performance",
                query="database benchmark",
                status="completed",
                summary="PostgreSQL result",
                sources_summary="Benchmark source",
            )
        ],
    )

    result = ContextAssembler().assemble(
        select_report_context(
            state
        )
    )

    assert (
        "PostgreSQL result"
        in result.rendered_text
    )

    assert (
        "Benchmark source"
        in result.rendered_text
    )


def test_report_context_contains_note_reference():
    state = SummaryState(
        research_topic="Topic",
        todo_items=[
            TodoItem(
                id=1,
                title="Task",
                intent="Intent",
                query="Query",
                note_id="note_123",
            )
        ],
    )

    result = ContextAssembler().assemble(
        select_report_context(
            state
        )
    )

    assert (
        "note_123"
        in result.rendered_text
    )


def test_report_context_is_read_only():
    state = SummaryState(
        research_topic="Topic",
        todo_items=[
            TodoItem(
                id=1,
                title="Task",
                intent="Intent",
                query="Query",
            )
        ],
    )

    original_topic = (
        state.research_topic
    )

    original_tasks = list(
        state.todo_items
    )

    select_report_context(
        state
    )

    assert (
        state.research_topic
        == original_topic
    )

    assert (
        state.todo_items
        == original_tasks
    )
