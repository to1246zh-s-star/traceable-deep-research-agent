"""User-facing presentation boundary for final research reports."""

from __future__ import annotations

import re
from collections.abc import Iterable

from models import SummaryState
from services.decision_reporting import (
    _canonical_constraint_statuses,
)

TECHNICAL_DECISION_SECTIONS = (
    "# 技术选型结论",
    "## 候选方案对比",
    "## 硬约束检查",
    "## 关键证据",
    "## 风险与未知",
    "## 推荐反转条件",
)

FORBIDDEN_INTERNAL_MARKERS = (
    "AUTHORITATIVE STRUCTURED DECISION STATE",
    "AUTHORITATIVE STRUCTURED STATE",
    "SOURCE-OF-TRUTH RULES",
    "SOURCE-OF-TRUTH",
    "DETERMINISTIC DECISION INTELLIGENCE CONTEXT",
    "NON-AUTHORITATIVE RESEARCH NARRATIVE",
    "NON-AUTHORITATIVE TASK NOTE REFERENCES",
    "PRIVATE GROUNDING CONTEXT",
    "USER-FACING PRESENTATION CONTRACT",
    "REPORT INSTRUCTION",
    "REPORTING POLICY",
    "RECOMPUTE AFFECTED MODULES",
    "COUNTERFACTUAL DEPENDENCY PATH",
    "CURRENT DECISION INTELLIGENCE DEPENDS",
    "HAS INSUFFICIENT CONFIDENCE",
    "HAS INSUFFICIENT COVERAGE",
    "NO EVIDENCE SIGNALS EXIST",
    "CANDIDATE ELIGIBILITY REMAINS UNRESOLVED",
    "integration_assessment",
    "decision_comparison",
    "decision_sensitivity",
    "recommendation_robustness",
    "research_gap_impact",
    "expected_decision_impact",
    "candidate_id",
    "criterion_id",
    "constraint_id",
    "decision_id",
    "evidence_id",
    "claim_id",
    "trace_id",
    "atomic_claim_id",
    "task_id",
    "note_id",
    "gap_id",
    "assumption_id",
    "trigger_id",
    "signal_id",
)

_INTERNAL_ID_RE = re.compile(
    r"\b(?:cand|crit|con|dec|evi|clm|aclm|trace|gap|asm|trigger|sig)_"
    r"[A-Za-z0-9][A-Za-z0-9_-]*\b",
    re.IGNORECASE,
)
_TASK_DUMP_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s*)?(?:任务|task)\s+\d+\s*[:：]",
    re.IGNORECASE | re.MULTILINE,
)
_RAW_JSON_RE = re.compile(
    r"```(?:json)?\s*[\[{]"
    r"|(?:^|\n)\s*[\[{]\s*(?:\n\s*)?\"[^\"\n]+\"\s*:",
    re.IGNORECASE,
)


def is_technical_decision_task(state: SummaryState) -> bool:
    """Return whether the persisted state represents a decision case."""
    return state.decision_case is not None


def build_user_report_contract(state: SummaryState) -> str:
    """Build presentation-only instructions for the reporting model."""
    shared = (
        "The context above is private grounding material, not report body.\n"
        "Output only a polished user-facing report for a technical decision "
        "maker or researcher.\n"
        "Never copy internal headers, source-of-truth instructions, raw JSON, "
        "execution/task dumps, trace data, or internal identifiers.\n"
        "Resolve candidates, criteria, and constraints to their user-facing "
        "names or descriptions.\n"
        "Preserve structured semantics exactly: UNKNOWN means unknown or "
        "insufficient evidence, never unsatisfied; missing evidence is not "
        "negative evidence; official/vendor material is not independent "
        "validation.\n"
        "Do not derive a recommendation from ranking or scores."
    )

    if not is_technical_decision_task(state):
        return (
            shared
            + "\nUse a natural research-report structure appropriate to the "
            "topic. The technical-decision section structure is not required."
        )

    sections = "\n".join(TECHNICAL_DECISION_SECTIONS)

    return (
        shared
        + "\nThis is a technical decision task. Use exactly these top-level "
        "sections in this order:\n"
        + sections
        + "\nAim for roughly 800–1500 Chinese characters when evidence permits; "
        "do not invent content to reach the target.\n"
        "A definitive recommendation is allowed only when the authoritative "
        "state contains a recommendation and its reporting policy permits it."
    )


def validate_user_report(
    report_text: str,
    state: SummaryState,
) -> bool:
    """Validate that a generated report obeys its presentation contract."""
    if not isinstance(report_text, str) or not report_text.strip():
        return False

    if _contains_internal_material(report_text):
        return False

    if not is_technical_decision_task(state):
        return True

    headings = [
        line.strip()
        for line in report_text.splitlines()
        if line.startswith("# ") or line.startswith("## ")
    ]

    return headings == list(TECHNICAL_DECISION_SECTIONS)


def render_user_facing_report(state: SummaryState) -> str:
    """Project authoritative state into the current presentation contract."""
    if is_technical_decision_task(state):
        return _build_technical_decision_fallback(state)

    stored_report = getattr(state, "structured_report", None)
    if (
        isinstance(stored_report, str)
        and validate_user_report(stored_report, state)
    ):
        return stored_report.strip()

    return _build_generic_research_fallback(state)


def build_fallback_user_report(state: SummaryState) -> str:
    """Backward-compatible name for the deterministic report projection."""
    return render_user_facing_report(state)


def _build_technical_decision_fallback(state: SummaryState) -> str:
    decision = state.decision_case
    assert decision is not None

    candidate_names = {
        candidate.candidate_id: _safe_text(candidate.name)
        or f"候选方案 {index}"
        for index, candidate in enumerate(decision.candidates, start=1)
    }
    constraint_names = {
        constraint.constraint_id: _safe_text(constraint.text)
        or f"硬约束 {index}"
        for index, constraint in enumerate(decision.constraints, start=1)
    }

    lines = [
        TECHNICAL_DECISION_SECTIONS[0],
        "",
        _recommendation_summary(state, candidate_names),
        "",
        TECHNICAL_DECISION_SECTIONS[1],
        "",
    ]

    comparison_lines = _comparison_projection(state, candidate_names)
    lines.extend(comparison_lines or ["当前没有可展示的候选方案比较结果。"])

    lines.extend(["", TECHNICAL_DECISION_SECTIONS[2], ""])
    constraint_lines = _constraint_projection(
        state,
        candidate_names,
        constraint_names,
    )
    lines.extend(constraint_lines or ["当前未记录硬约束。"])

    lines.extend(["", TECHNICAL_DECISION_SECTIONS[3], ""])
    lines.extend(_evidence_projection(state))

    lines.extend(["", TECHNICAL_DECISION_SECTIONS[4], ""])
    lines.extend(_risk_projection(state))

    lines.extend(["", TECHNICAL_DECISION_SECTIONS[5], ""])
    lines.extend(_reversal_projection(state))

    return "\n".join(lines).strip()


def _recommendation_summary(
    state: SummaryState,
    candidate_names: dict[str, str],
) -> str:
    decision = state.decision_case
    assert decision is not None

    recommendation = _safe_text(decision.recommendation)
    readiness_status = str(
        getattr(state.decision_readiness, "status", "UNKNOWN") or "UNKNOWN"
    ).upper()

    status_labels = {
        "READY": "已就绪",
        "INSUFFICIENT_EVIDENCE": "证据不足",
        "NOT_READY": "尚未就绪",
    }
    status_label = status_labels.get(readiness_status, "待确认")

    if recommendation and readiness_status == "READY":
        return f"决策状态：{status_label}\n\n推荐：{recommendation}"

    if recommendation:
        return (
            f"决策状态：{status_label}\n\n"
            "推荐：暂不形成确定推荐\n\n"
            f"当前结构化状态记录的暂定方向为“{recommendation}”，"
            "但在决策就绪前不能将其作为正式推荐。"
        )

    names = [name for name in candidate_names.values() if name]
    candidate_scope = "、".join(names[:3]) or "各候选方案"
    return (
        f"决策状态：{status_label}\n\n"
        "推荐：暂不形成确定推荐\n\n"
        "当前关键约束与评价维度仍存在证据覆盖不足，因此系统保留未知项，"
        f"不基于缺失证据强行选择{candidate_scope}。"
    )


def _comparison_projection(
    state: SummaryState,
    candidate_names: dict[str, str],
) -> list[str]:
    decision = state.decision_case
    assert decision is not None

    criteria = sorted(
        enumerate(decision.criteria),
        key=lambda item: (-float(item[1].weight), item[0]),
    )[:4]
    candidates = list(decision.candidates)[:4]

    if not criteria or not candidates:
        return [
            f"- {candidate_names[candidate.candidate_id]}"
            for candidate in candidates
        ]

    directions_by_pair: dict[tuple[str, str], set[str]] = {}
    for signal in state.evidence_signals:
        key = (signal.candidate_id, signal.criterion_id)
        directions_by_pair.setdefault(key, set()).add(
            str(signal.direction or "").lower()
        )

    criterion_values = [item[1] for item in criteria]
    lines = [
        "以下为评价维度的独立候选比较状态；硬约束是否满足以"
        "“硬约束检查”章节为准。",
        "",
        "| 候选方案 | "
        + " | ".join(
            _table_cell(_safe_text(criterion.name) or "未命名维度")
            for criterion in criterion_values
        )
        + " |",
        "|---|" + "---|" * len(criterion_values),
    ]

    for candidate in candidates:
        cells = [
            _signal_presentation(
                directions_by_pair.get(
                    (candidate.candidate_id, criterion.criterion_id),
                    set(),
                )
            )
            for criterion in criterion_values
        ]
        lines.append(
            "| "
            + _table_cell(candidate_names[candidate.candidate_id])
            + " | "
            + " | ".join(cells)
            + " |"
        )

    lines.append(
        "\n> ✅ / ⚠️ 仅表示已有结构化候选比较信号；— 表示当前尚未形成"
        "独立的候选比较结论。硬约束是否满足以“硬约束检查”章节为准。"
    )
    return lines


def _constraint_projection(
    state: SummaryState,
    candidate_names: dict[str, str],
    constraint_names: dict[str, str],
) -> list[str]:
    status_labels = {
        "SATISFIED": "满足",
        "UNSATISFIED": "不满足",
        "UNKNOWN": "未知（当前证据不足，尚待验证）",
    }
    rows: list[str] = []

    for row in _canonical_constraint_statuses(state):
        candidate_name = candidate_names.get(row["candidate_id"])
        constraint_name = constraint_names.get(row["constraint_id"])
        if candidate_name is None or constraint_name is None:
            continue

        status = str(row["status"] or "UNKNOWN").upper()
        label = status_labels.get(
            status,
            "未知（当前证据不足，尚待验证）",
        )
        rows.append(
            f"| {_table_cell(candidate_name)} | "
            f"{_table_cell(constraint_name)} | {label} |"
        )

    if not rows:
        return []

    return [
        "| 候选方案 | 硬约束 | 当前状态 |",
        "|---|---|---|",
        *rows,
    ]


def _evidence_projection(state: SummaryState) -> list[str]:
    assessments = list(state.evidence_assessments or [])
    lines = [
        f"- 当前保留 {len(state.evidence_items)} 项 Evidence，"
        f"并形成 {len(state.claims)} 个可追踪 Claim。"
    ]

    authority_labels = {
        "OFFICIAL_DOCUMENTATION": "官方文档",
        "OFFICIAL_SECURITY": "官方安全材料",
        "OFFICIAL_PRICING": "官方定价材料",
        "OFFICIAL_RELEASE_NOTES": "官方发布说明",
        "VENDOR": "厂商材料",
        "INDEPENDENT_BENCHMARK": "独立基准",
        "INDEPENDENT_TECHNICAL": "独立技术分析",
        "ACADEMIC": "学术来源",
        "COMMUNITY": "社区来源",
        "NEWS": "新闻来源",
        "ISSUE_TRACKER": "问题跟踪记录",
        "SOURCE_REPOSITORY": "源代码仓库",
    }
    authorities = sorted(
        {
            authority_labels[authority]
            for assessment in assessments
            if (
                (authority := assessment.source_quality.authority_type)
                in authority_labels
            )
        }
    )
    if authorities:
        visible = authorities[:5]
        suffix = "等" if len(authorities) > len(visible) else ""
        lines.append(
            "- 来源类型覆盖：" + "、".join(visible) + suffix + "。"
        )
    elif assessments:
        lines.append("- 来源权威类型尚未确认。")

    if not assessments:
        lines.append("- 当前证据不足，尚不能据此扩大结论。")

    if any(
        str(assessment.source_quality.authority_type or "").startswith(
            "OFFICIAL_"
        )
        or assessment.source_quality.authority_type == "VENDOR"
        for assessment in assessments
    ):
        lines.append("- 官方或厂商材料不等同于独立验证。")

    return lines


def _risk_projection(state: SummaryState) -> list[str]:
    decision = state.decision_case
    assert decision is not None
    candidate_names = {
        candidate.candidate_id: _safe_text(candidate.name)
        or f"候选方案 {index}"
        for index, candidate in enumerate(decision.candidates, start=1)
    }
    criterion_names = {
        criterion.criterion_id: _safe_text(criterion.name)
        or f"评价维度 {index}"
        for index, criterion in enumerate(decision.criteria, start=1)
    }
    lines: list[str] = []
    analysis = state.research_analysis
    uncovered = _ordered_unique(
        criterion_names.get(coverage.criterion_id)
        for coverage in getattr(analysis, "coverages", []) or []
        if coverage.signal_count == 0
    )
    if uncovered:
        lines.append(
            "- 独立候选比较层面的证据覆盖不足，涉及关键维度："
            + "、".join(uncovered[:4])
            + ("等" if len(uncovered) > 4 else "")
            + "。"
        )

    gaps_by_candidate: dict[str, list[str]] = {}
    for gap in getattr(analysis, "research_gaps", []) or []:
        if getattr(gap, "status", "open") == "resolved":
            continue
        candidate_name = candidate_names.get(gap.candidate_id)
        criterion_name = criterion_names.get(gap.criterion_id)
        if candidate_name and criterion_name:
            gaps_by_candidate.setdefault(candidate_name, []).append(
                criterion_name
            )

    for candidate_name, names in list(gaps_by_candidate.items())[:2]:
        unique_names = _ordered_unique(names)
        lines.append(
            f"- 在独立候选比较层面，{candidate_name} 的"
            + "、".join(unique_names[:4])
            + ("等维度" if len(unique_names) > 4 else "方面")
            + "仍缺少足够的结构化证据信号。"
        )

    team_context = [
        text
        for value in getattr(state.technical_context, "team_capabilities", [])
        if (text := _safe_text(value))
    ]
    if team_context:
        lines.append(
            f"- 团队背景“{team_context[0]}”来自用户提供的技术上下文，"
            "不属于外部验证证据。"
        )

    lines.append(
        "- 未知项仅表示当前无法验证，不能据此判断为满足或不满足。"
    )

    return lines[:5]


def _reversal_projection(state: SummaryState) -> list[str]:
    decision = state.decision_case
    assert decision is not None

    criterion_names = {
        criterion.criterion_id: _safe_text(criterion.name)
        for criterion in decision.criteria
    }
    field_labels = {
        "team_capabilities": "团队能力或技术栈",
        "scale_requirements": "数据规模、并发或水平扩展要求",
        "performance_requirements": "性能与复杂查询要求",
        "reliability_requirements": "一致性与可靠性要求",
        "deployment_environment": "部署环境",
        "infrastructure": "基础设施条件",
        "integration_requirements": "集成要求",
        "operational_constraints": "运维约束",
        "security_constraints": "安全约束",
        "compliance_constraints": "合规约束",
        "migration_constraints": "迁移约束",
        "budget_constraints": "预算约束",
    }
    context_values: dict[str, list[str]] = {}
    priority_names: list[str] = []
    semantic_order: list[tuple[str, str]] = []

    for trigger in state.decision_reevaluation_triggers:
        trigger_type = str(
            getattr(trigger, "trigger_type", "")
            or ""
        ).upper()

        if trigger_type == "TECHNICAL_CONTEXT_CHANGE":
            source_field = str(getattr(trigger, "source_field", "") or "")
            if source_field not in field_labels:
                continue
            key = ("context", source_field)
            if key not in semantic_order:
                semantic_order.append(key)
            values = context_values.setdefault(source_field, [])
            if (
                (source_value := _safe_text(getattr(trigger, "source_value", None)))
                and source_value not in values
            ):
                values.append(source_value)

        elif trigger_type == "CRITERION_PRIORITY_CHANGE":
            names = [
                criterion_names[criterion_id]
                for criterion_id in getattr(
                    trigger,
                    "affected_criterion_ids",
                    [],
                )
                if criterion_names.get(criterion_id)
            ]
            for name in names:
                if name not in priority_names:
                    priority_names.append(name)
            key = ("priority", "criteria")
            if names and key not in semantic_order:
                semantic_order.append(key)

    lines: list[str] = []
    for kind, key in semantic_order:
        if len(lines) >= 5:
            break

        if kind == "priority":
            lines.append(
                "- 若“"
                + "、".join(priority_names[:4])
                + ("等" if len(priority_names) > 4 else "")
                + "”的优先级发生变化，应重新评估候选比较。"
            )
            continue

        values = context_values.get(key, [])
        current = (
            "（当前记录：" + "；".join(values[:2]) + "）"
            if values
            else ""
        )
        lines.append(
            f"- 若{field_labels[key]}发生变化{current}，应重新评估。"
        )

    if lines:
        if not _safe_text(decision.recommendation):
            return [
                "当前尚无正式推荐；以下内容是重新评估条件，"
                "不是既定推荐的反转结论。",
                "",
                *lines,
            ]

        return lines

    if _safe_text(decision.recommendation):
        return ["- 系统尚未记录明确的推荐反转条件。"]

    return ["- 由于尚无正式推荐，目前不存在可判定的推荐反转条件。"]


def _build_generic_research_fallback(state: SummaryState) -> str:
    topic = _safe_text(state.research_topic) or "研究主题未提供"
    findings: list[str] = []
    sources: list[str] = []

    if summary := _safe_text(state.running_summary):
        findings.append(summary)

    if not findings:
        for task in state.todo_items:
            summary = _safe_text(task.summary)
            if not summary:
                continue
            title = _safe_text(task.title)
            findings.append(f"- {title}：{summary}" if title else f"- {summary}")

    for task in state.todo_items:
        if source_summary := _safe_text(task.sources_summary):
            sources.append(f"- {source_summary}")

    lines = [
        "# 研究报告",
        "",
        "## 研究主题",
        "",
        topic,
        "",
        "## 主要发现",
        "",
    ]
    lines.extend(findings or ["当前没有可展示的研究结论。"])
    lines.extend(["", "## 来源概览", ""])
    lines.extend(sources or ["当前没有可展示的来源概览。"])
    lines.extend(
        [
            "",
            "## 局限",
            "",
            "本报告仅汇总已保存的研究结果，不补充未被现有材料支持的结论。",
        ]
    )

    return "\n".join(lines).strip()


def _signal_presentation(directions: set[str]) -> str:
    if not directions or directions <= {"neutral", ""}:
        return "— 暂无独立比较结论"
    if "positive" in directions and "negative" in directions:
        return "⚠️ 证据冲突"
    if "positive" in directions:
        return "✅ 有支持证据"
    if "negative" in directions:
        return "⚠️ 有反向证据"
    return "— 暂无独立比较结论"


def _table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _ordered_unique(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _safe_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text or _contains_internal_material(text):
        return None

    return text


def _contains_internal_material(text: str) -> bool:
    folded = text.casefold()

    if any(marker.casefold() in folded for marker in FORBIDDEN_INTERNAL_MARKERS):
        return True

    return bool(
        _INTERNAL_ID_RE.search(text)
        or _TASK_DUMP_HEADING_RE.search(text)
        or _RAW_JSON_RE.search(text)
    )
