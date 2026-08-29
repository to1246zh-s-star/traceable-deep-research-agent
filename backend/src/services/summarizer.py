"""Task summarization utilities."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Tuple

from hello_agents import ToolAwareSimpleAgent

from models import SummaryState, TodoItem

from services.context_engineering import (
    ContextAssembler,
    ContextBudget,
    ContextBudgetPlanner,
    selection_from_budget_result,
)
from services.summarizer_context import (
    select_summarizer_context,
)
from config import Configuration
from utils import strip_thinking_tokens
from services.notes import build_note_guidance
from services.text_processing import strip_tool_calls


SUMMARIZER_CONTEXT_MAX_UNITS = 12000
SUMMARIZER_RESERVED_OUTPUT_UNITS = 2000


SUMMARIZER_CONTEXT_MAX_UNITS = 12000
SUMMARIZER_RESERVED_OUTPUT_UNITS = 2000


class SummarizationService:
    """Handles synchronous and streaming task summarization."""

    INVALID_SUMMARY_MARKERS = (
        "🔧 工具",
        "工具 note 执行结果",
        "笔记创建成功",
        "笔记更新成功",
        "请基于这些结果给出完整的回答",
        "暂无可用信息",
    )

    def __init__(
        self,
        summarizer_factory: Callable[[], ToolAwareSimpleAgent],
        config: Configuration,
    ) -> None:
        self._agent_factory = summarizer_factory
        self._config = config

    def summarize_task(self, state: SummaryState, task: TodoItem, context: str) -> str:
        """Generate a task-specific summary using the summarizer agent."""

        prompt = self._build_prompt(state, task, context)

        agent = self._agent_factory()
        try:
            response = agent.run(prompt)
        finally:
            agent.clear_history()

        summary_text = response.strip()
        if self._config.strip_thinking_tokens:
            summary_text = strip_thinking_tokens(summary_text)

        summary_text = strip_tool_calls(summary_text).strip()

        return summary_text or "暂无可用信息"

    def is_valid_summary(self, text: str | None) -> bool:
        """判断模型输出是否为可展示的任务总结。"""

        if not text:
            return False

        cleaned = text.strip()

        if len(cleaned) < 120:
            return False

        if any(marker in cleaned for marker in self.INVALID_SUMMARY_MARKERS):
            return False

        return True

    def stream_task_summary(
        self, state: SummaryState, task: TodoItem, context: str
    ) -> Tuple[Iterator[str], Callable[[], str]]:
        """Stream the summary text for a task while collecting full output."""

        prompt = self._build_prompt(state, task, context)
        remove_thinking = self._config.strip_thinking_tokens
        raw_buffer = ""
        visible_output = ""
        emit_index = 0
        agent = self._agent_factory()

        def flush_visible() -> Iterator[str]:
            nonlocal emit_index, raw_buffer
            while True:
                start = raw_buffer.find("<think>", emit_index)
                if start == -1:
                    if emit_index < len(raw_buffer):
                        segment = raw_buffer[emit_index:]
                        emit_index = len(raw_buffer)
                        if segment:
                            yield segment
                    break

                if start > emit_index:
                    segment = raw_buffer[emit_index:start]
                    emit_index = start
                    if segment:
                        yield segment

                end = raw_buffer.find("</think>", start)
                if end == -1:
                    break
                emit_index = end + len("</think>")

        def generator() -> Iterator[str]:
            nonlocal raw_buffer, visible_output, emit_index
            try:
                for chunk in agent.stream_run(prompt):
                    raw_buffer += chunk
                    if remove_thinking:
                        for segment in flush_visible():
                            visible_output += segment
                            if segment:
                                yield segment
                    else:
                        visible_output += chunk
                        if chunk:
                            yield chunk
            finally:
                if remove_thinking:
                    for segment in flush_visible():
                        visible_output += segment
                        if segment:
                            yield segment
                agent.clear_history()

        def get_summary() -> str:
            if remove_thinking:
                cleaned = strip_thinking_tokens(visible_output)
            else:
                cleaned = visible_output

            return strip_tool_calls(cleaned).strip()

        return generator(), get_summary

    def _build_prompt(
        self,
        state: SummaryState,
        task: TodoItem,
        context: str,
    ) -> str:
        """Construct the summarization prompt shared by both modes."""

        context_selection = (
            select_summarizer_context(
                state,
                task,
                context,
            )
        )

        budget_result = (
            ContextBudgetPlanner().apply(
                context_selection,
                ContextBudget(
                    max_units=
                        SUMMARIZER_CONTEXT_MAX_UNITS,
                    reserved_output_units=
                        SUMMARIZER_RESERVED_OUTPUT_UNITS,
                ),
            )
        )

        budgeted_selection = (
            selection_from_budget_result(
                budget_result
            )
        )

        assembled_context = (
            ContextAssembler().assemble(
                budgeted_selection
            )
        )

        return (
            f"{assembled_context.rendered_text}\n\n"
            "SUMMARIZATION INSTRUCTION:\n"
            f"{build_note_guidance(task)}\n"
            "请按照以上协作要求先同步笔记，然后返回一份"
            "面向用户的 Markdown 总结"
            "（仍遵循任务总结模板）。"
        )

