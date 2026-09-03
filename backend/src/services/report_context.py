"""Context selection for final report generation."""

from __future__ import annotations

from models import SummaryState

from services.context_engineering import (
    CONTEXT_PRIORITY_CRITICAL,
    CONTEXT_PRIORITY_NORMAL,
    ContextSection,
    ContextSelection,
)

from services.decision_reporting import (
    build_decision_reporting_context,
)


def select_report_context(
    state: SummaryState,
) -> ContextSelection:
    """
    Select persisted research state needed for final report generation.

    This function only selects and formats existing state.
    It must not infer new evidence, scores, or recommendations.
    """

    sections: list[
        ContextSection
    ] = []

    sections.append(
        ContextSection(
            name="Research Topic",
            content=(
                f"研究主题：{state.research_topic}"
                if state.research_topic
                else ""
            ),
            priority=
                CONTEXT_PRIORITY_CRITICAL,
            required=True,
        )
    )

    decision_context = (
        build_decision_reporting_context(
            state
        )
    )

    if decision_context:
        sections.append(
            ContextSection(
                name="AUTHORITATIVE STRUCTURED STATE",
                content=decision_context,
                priority=
                    CONTEXT_PRIORITY_CRITICAL,
                required=True,
            )
        )

    task_blocks: list[str] = []

    source_ids: list[str] = []

    for task in state.todo_items:
        summary = (
            task.summary
            or "暂无可用信息"
        )

        sources = (
            task.sources_summary
            or "暂无来源"
        )

        task_blocks.append(
            "\n".join(
                [
                    (
                        f"### 任务 "
                        f"{task.id}: "
                        f"{task.title}"
                    ),
                    (
                        f"- 任务目标："
                        f"{task.intent}"
                    ),
                    (
                        f"- 检索查询："
                        f"{task.query}"
                    ),
                    (
                        f"- 执行状态："
                        f"{task.status}"
                    ),
                    "- 任务总结：",
                    summary,
                    "- 来源概览：",
                    sources,
                ]
            )
        )

        for evidence_id in getattr(
            task,
            "evidence_ids",
            [],
        ):
            source_ids.append(
                str(evidence_id)
            )

    if task_blocks:
        sections.append(
            ContextSection(
                name="NON-AUTHORITATIVE RESEARCH NARRATIVE",
                content="\n\n".join(
                    task_blocks
                ),
                priority=
                    CONTEXT_PRIORITY_NORMAL,
                source_ids=tuple(
                    source_ids
                ),
            )
        )

    note_references: list[str] = []

    for task in state.todo_items:
        if not task.note_id:
            continue

        note_references.append(
            (
                f"- 任务 {task.id}"
                f"《{task.title}》："
                f"note_id={task.note_id}"
            )
        )

    if note_references:
        sections.append(
            ContextSection(
                name="NON-AUTHORITATIVE TASK NOTE REFERENCES",
                content="\n".join(
                    note_references
                ),
                priority=
                    CONTEXT_PRIORITY_NORMAL,
            )
        )

    return ContextSelection(
        purpose="final_report",
        sections=tuple(
            sections
        ),
    )
