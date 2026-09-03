"""Service that consolidates task results into the final report."""

from __future__ import annotations

import json
import logging

from hello_agents import ToolAwareSimpleAgent

from config import Configuration
from models import SummaryState
from services.context_engineering import ContextAssembler
from services.llm_runtime_circuit import (
    is_llm_circuit_open,
    open_llm_circuit_from_error,
    record_circuit_skip,
)
from services.report_context import select_report_context
from services.report_presentation import (
    build_fallback_user_report,
    build_user_report_contract,
    validate_user_report,
)
from services.runtime_notices import record_runtime_notice
from services.text_processing import strip_tool_calls
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)


class ReportingService:
    """Generates the final structured report."""

    def __init__(self, report_agent: ToolAwareSimpleAgent, config: Configuration) -> None:
        """Initialize the service with its reporting agent and configuration."""
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

        presentation_contract = (
            build_user_report_contract(state)
        )

        prompt = (
            "PRIVATE GROUNDING CONTEXT — DO NOT COPY INTO THE FINAL REPORT:\n"
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
            "USER-FACING PRESENTATION CONTRACT:\n"
            f"{presentation_contract}\n"
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

        if validate_user_report(
            report_text,
            state,
        ):
            return report_text

        logger.warning(
            "Final report LLM violated presentation contract; "
            "using deterministic fallback report"
        )

        record_runtime_notice(
            state,
            stage="report_presentation_validation",
            error=ValueError(
                "Final report violated the user-facing presentation contract"
            ),
            degraded=True,
            metadata={
                "fallback": "deterministic",
                "reason": "presentation_contract_violation",
            },
        )

        return self._build_fallback_report(state)

    @staticmethod
    def _build_fallback_report(
        state: SummaryState,
    ) -> str:
        """Build a deterministic report when the reporting LLM is unavailable.

        This fallback only summarizes already persisted research state.
        It must not invent candidate scores, evidence, or recommendations.
        """
        return build_fallback_user_report(state)

