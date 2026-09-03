"""Service that consolidates task results into the final report."""

from __future__ import annotations

import json
import logging

from hello_agents import ToolAwareSimpleAgent

from models import SummaryState
from config import Configuration
from utils import strip_thinking_tokens
from services.text_processing import strip_tool_calls
from services.context_engineering import ContextAssembler
from services.report_context import select_report_context
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

        context_selection = (
            select_report_context(
                state
            )
        )

        assembled_context = (
            ContextAssembler().assemble(
                context_selection
            )
        )

        read_template = json.dumps(
            {
                "action": "read",
                "note_id": "<note_id>",
            },
            ensure_ascii=False,
        )

        create_conclusion_template = json.dumps(
            {
                "action": "create",
                "title": (
                    f"研究报告："
                    f"{state.research_topic}"
                ),
                "note_type": "conclusion",
                "tags": [
                    "deep_research",
                    "report",
                ],
                "content": (
                    "请在此沉淀最终报告要点"
                ),
            },
            ensure_ascii=False,
        )

        prompt = (
            f"{assembled_context.rendered_text}\n\n"
            "REPORT INSTRUCTION:\n"
            "SOURCE-OF-TRUTH PRECEDENCE:\n"
            "1. AUTHORITATIVE STRUCTURED STATE controls factual conclusions.\n"
            "2. NON-AUTHORITATIVE RESEARCH NARRATIVE is supporting material only.\n"
            "3. On conflict, ignore narrative and preserve structured status.\n"
            "4. UNKNOWN is uncertainty, never FALSE or UNSATISFIED.\n"
            "5. Missing evidence is not evidence of absence.\n"
            "请基于以上上下文撰写最终研究报告。"
            "不要补造不存在的 evidence、candidate score、"
            "constraint judgment 或 recommendation。\n"
            f"如需读取任务笔记，请使用："
            f"[TOOL_CALL:note:{read_template}]\n"
            f"如需保存汇总结论，可使用："
            f"[TOOL_CALL:note:{create_conclusion_template}]"
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

        decision_truth = build_decision_reporting_context(
            state
        )

        if decision_truth:
            lines.extend(
                [
                    "## AUTHORITATIVE STRUCTURED STATE",
                    "",
                    decision_truth,
                    "",
                ]
            )

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

        lines.extend(
            [
                "## NON-AUTHORITATIVE RESEARCH NARRATIVE",
                "",
                (
                    "Task summaries below are supporting narrative only; "
                    "they cannot override authoritative structured state."
                ),
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

