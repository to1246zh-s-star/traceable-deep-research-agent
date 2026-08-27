"""Service that consolidates task results into the final report."""

from __future__ import annotations

import json
import logging

from hello_agents import ToolAwareSimpleAgent

from models import SummaryState
from config import Configuration
from utils import strip_thinking_tokens
from services.text_processing import strip_tool_calls
from services.decision_reporting import build_decision_reporting_context
from services.runtime_notices import record_runtime_notice
from services.llm_runtime_circuit import (
    is_llm_circuit_open,
    open_llm_circuit_from_error,
    record_circuit_skip,
)

logger = logging.getLogger(__name__)


class ReportingService:
    """Generates the final structured report."""

    def __init__(self, report_agent: ToolAwareSimpleAgent, config: Configuration) -> None:
        self._agent = report_agent
        self._config = config

    def generate_report(self, state: SummaryState) -> str:
        """Generate a structured report based on completed tasks."""

        tasks_block = []
        for task in state.todo_items:
            summary_block = task.summary or "暂无可用信息"
            sources_block = task.sources_summary or "暂无来源"
            tasks_block.append(
                f"### 任务 {task.id}: {task.title}\n"
                f"- 任务目标：{task.intent}\n"
                f"- 检索查询：{task.query}\n"
                f"- 执行状态：{task.status}\n"
                f"- 任务总结：\n{summary_block}\n"
                f"- 来源概览：\n{sources_block}\n"
            )

        note_references = []
        for task in state.todo_items:
            if task.note_id:
                note_references.append(
                    f"- 任务 {task.id}《{task.title}》：note_id={task.note_id}"
                )

        notes_section = "\n".join(note_references) if note_references else "- 暂无可用任务笔记"

        read_template = json.dumps({"action": "read", "note_id": "<note_id>"}, ensure_ascii=False)
        create_conclusion_template = json.dumps(
            {
                "action": "create",
                "title": f"研究报告：{state.research_topic}",
                "note_type": "conclusion",
                "tags": ["deep_research", "report"],
                "content": "请在此沉淀最终报告要点",
            },
            ensure_ascii=False,
        )

        decision_context = (
            build_decision_reporting_context(
                state
            )
        )

        decision_section = (
            f"{decision_context}\n\n"
            if decision_context
            else ""
        )

        prompt = (
            f"研究主题：{state.research_topic}\n"
            f"{decision_section}"
            f"任务概览：\n{''.join(tasks_block)}\n"
            f"可用任务笔记：\n{notes_section}\n"
            f"请针对每条任务笔记使用格式：[TOOL_CALL:note:{read_template}] 读取内容，整合所有信息后撰写报告。\n"
            f"如需输出汇总结论，可追加调用：[TOOL_CALL:note:{create_conclusion_template}] 保存报告要点。"
        )

        if is_llm_circuit_open(state):
            record_circuit_skip(
                state,
                stage="report_generation",
            )
            return self._build_fallback_report(
                state
            )

        try:
            response = self._agent.run(prompt)
            self._agent.clear_history()
        except Exception as exc:
            logger.exception(
                "Final report LLM failed; using deterministic fallback report"
            )

            open_llm_circuit_from_error(
                state,
                error=exc,
                trigger_stage="report_generation",
            )

            record_runtime_notice(
                state,
                stage="report_generation",
                error=exc,
                degraded=True,
                metadata={
                    "fallback": "deterministic",
                },
            )

            try:
                self._agent.clear_history()
            except Exception:
                pass

            return self._build_fallback_report(state)

        report_text = (response or "").strip()

        if self._config.strip_thinking_tokens:
            report_text = strip_thinking_tokens(report_text)

        report_text = strip_tool_calls(report_text).strip()

        if report_text:
            return report_text

        logger.warning(
            "Final report LLM returned empty output; "
            "using deterministic fallback report"
        )
        return self._build_fallback_report(state)

    @staticmethod
    def _build_fallback_report(
        state: SummaryState,
    ) -> str:
        """
        Build a deterministic report when the final reporting LLM is
        unavailable.

        This fallback only summarizes already persisted research state.
        It must not invent candidate scores, evidence, or recommendations.
        """

        lines = [
            "# 研究报告",
            "",
            "## 背景概览",
            "",
            f"研究主题：{state.research_topic}",
            "",
        ]

        decision = state.decision_case
        readiness = state.decision_readiness

        if decision is not None and readiness is not None:
            status = str(
                readiness.status or "UNKNOWN"
            ).upper()

            lines.extend(
                [
                    "## 决策状态",
                    "",
                    f"- Decision readiness: **{status}**",
                    (
                        f"- Readiness score: "
                        f"{readiness.overall_score:.3f}"
                    ),
                ]
            )

            stopping = state.stopping_decision

            if stopping is not None:
                lines.extend(
                    [
                        f"- Research stopping reason: `{stopping.reason}`",
                        (
                            "- Remaining actionable research gaps: "
                            f"{stopping.actionable_gap_count}"
                        ),
                    ]
                )

            if status == "READY":
                lines.extend(
                    [
                        "",
                        (
                            "当前 deterministic decision state 已达到 "
                            "READY，但由于最终报告模型不可用，本降级报告"
                            "不会自行生成或扩大新的推荐结论。"
                        ),
                    ]
                )
            else:
                lines.extend(
                    [
                        "",
                        (
                            "当前决策尚未达到可输出确定性生产选型的状态。"
                            "以下内容仅整理已有研究结果，不构成最终技术选型。"
                        ),
                    ]
                )

            blocking = list(
                readiness.blocking_reasons or []
            )

            if blocking:
                lines.extend(
                    [
                        "",
                        "### 未解决的决策阻塞项",
                        "",
                    ]
                )
                lines.extend(
                    f"- {reason}"
                    for reason in blocking
                )

            lines.append("")

        lines.extend(
            [
                "## 核心研究结果",
                "",
            ]
        )

        completed_any = False

        for task in state.todo_items:
            summary = (
                task.summary
                or ""
            ).strip()

            if not summary:
                continue

            completed_any = True

            lines.extend(
                [
                    f"### 任务 {task.id}: {task.title}",
                    "",
                    f"- 执行状态：{task.status}",
                    "",
                    summary,
                    "",
                ]
            )

        if not completed_any:
            lines.extend(
                [
                    "当前没有可用的任务总结。",
                    "",
                ]
            )

        lines.extend(
            [
                "## 来源与可追溯性",
                "",
            ]
        )

        source_any = False

        for task in state.todo_items:
            sources = (
                task.sources_summary
                or ""
            ).strip()

            if not sources:
                continue

            source_any = True

            lines.extend(
                [
                    f"### 任务 {task.id}: {task.title}",
                    "",
                    sources,
                    "",
                ]
            )

        if not source_any:
            lines.extend(
                [
                    "暂无可用来源摘要。",
                    "",
                ]
            )

        lines.extend(
            [
                "## 报告状态",
                "",
                (
                    "最终报告生成模型暂时不可用；本报告由系统根据"
                    "已完成任务和已持久化决策状态进行确定性降级整理。"
                ),
            ]
        )

        return "\n".join(lines).strip()

