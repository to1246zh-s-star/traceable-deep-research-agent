"""Context selection for task summarization."""

from __future__ import annotations

from models import (
    SummaryState,
    TodoItem,
)

from services.context_engineering import (
    CONTEXT_PRIORITY_CRITICAL,
    CONTEXT_PRIORITY_HIGH,
    CONTEXT_PRIORITY_NORMAL,
    ContextSection,
    ContextSelection,
)


def select_summarizer_context(
    state: SummaryState,
    task: TodoItem,
    context: str,
) -> ContextSelection:
    """
    Select existing task/research context for one summarization call.

    This function is read-only. It must not infer new evidence,
    mutate task state, or convert retrieved observations into truth.
    """

    sections: list[
        ContextSection
    ] = []

    sections.append(
        ContextSection(
            name="Research Topic",
            content=(
                f"任务主题：{state.research_topic}"
                if state.research_topic
                else ""
            ),
            priority=
                CONTEXT_PRIORITY_CRITICAL,
            required=True,
        )
    )

    task_metadata = "\n".join(
        [
            f"任务名称：{task.title}",
            f"任务目标：{task.intent}",
            f"检索查询：{task.query}",
        ]
    )

    sections.append(
        ContextSection(
            name="Task",
            content=task_metadata,
            priority=
                CONTEXT_PRIORITY_HIGH,
            required=True,
        )
    )

    normalized_context = (
        context or ""
    ).strip()

    if normalized_context:
        sections.append(
            ContextSection(
                name="Task Context",
                content=(
                    "任务上下文：\n"
                    f"{normalized_context}"
                ),
                priority=
                    CONTEXT_PRIORITY_NORMAL,
            )
        )

    return ContextSelection(
        purpose="task_summary",
        sections=tuple(
            sections
        ),
    )
