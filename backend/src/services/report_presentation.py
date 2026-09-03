"""User-facing presentation boundary for final research reports."""

from __future__ import annotations

import re

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


def build_fallback_user_report(state: SummaryState) -> str:
    """Project persisted state into a deterministic user-facing report."""
    if is_technical_decision_task(state):
        return _build_technical_decision_fallback(state)

    return _build_generic_research_fallback(state)


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

    if recommendation and readiness_status == "READY":
        return f"正式建议：{recommendation}"

    if recommendation:
        return (
            f"当前记录的建议为“{recommendation}”，但决策状态尚未就绪，"
            "因此该建议仅作为暂定方向。"
        )

    ranked_names = _known_candidate_names(
        getattr(state.decision_comparison, "ranked_candidate_ids", []),
        candidate_names,
    )

    if ranked_names:
        return (
            f"当前证据下 {ranked_names[0]} 综合表现靠前，但系统尚未形成"
            "确定推荐；比较结果不等于正式建议。"
        )

    return "系统尚未形成确定推荐，现有信息仅支持继续比较与验证。"


def _comparison_projection(
    state: SummaryState,
    candidate_names: dict[str, str],
) -> list[str]:
    decision = state.decision_case
    assert decision is not None

    lines = [
        f"- {candidate_names[candidate.candidate_id]}"
        + (
            f"：{description}"
            if (description := _safe_text(candidate.description))
            else ""
        )
        for candidate in decision.candidates
    ]

    comparison = state.decision_comparison
    ranked_names = _known_candidate_names(
        getattr(comparison, "ranked_candidate_ids", []),
        candidate_names,
    )
    if ranked_names:
        lines.append(
            "- 当前确定性比较顺序："
            + " > ".join(ranked_names)
            + "。该顺序仅描述比较结果。"
        )

    unresolved_names = _known_candidate_names(
        getattr(comparison, "unresolved_candidate_ids", []),
        candidate_names,
    )
    if unresolved_names:
        lines.append(
            "- 尚待验证的候选方案：" + "、".join(unresolved_names) + "。"
        )

    excluded_names = _known_candidate_names(
        getattr(comparison, "excluded_candidate_ids", []),
        candidate_names,
    )
    if excluded_names:
        lines.append(
            "- 已由现有决策逻辑排除的候选方案："
            + "、".join(excluded_names)
            + "。"
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
    lines: list[str] = []

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
        lines.append(f"- {candidate_name}｜{constraint_name}：{label}")

    return lines


def _evidence_projection(state: SummaryState) -> list[str]:
    assessments = list(state.evidence_assessments or [])
    lines = [f"- 已评估证据 {len(assessments)} 项。"]

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
        lines.append("- 来源覆盖：" + "、".join(authorities) + "。")
    elif assessments:
        lines.append("- 来源权威类型尚未确认。")

    grounded_claims = []
    for claim in state.atomic_claims:
        if str(claim.grounding_status).lower() != "grounded":
            continue
        text = _safe_text(claim.text)
        if text:
            grounded_claims.append(text)
        if len(grounded_claims) == 3:
            break

    lines.extend(f"- 已核验陈述：{text}" for text in grounded_claims)

    if not assessments and not grounded_claims:
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
    lines: list[str] = []
    readiness = state.decision_readiness

    for reason in getattr(readiness, "blocking_reasons", []) or []:
        if text := _safe_text(reason):
            lines.append(f"- 决策阻碍：{text}")

    analysis = state.research_analysis
    for gap in getattr(analysis, "research_gaps", []) or []:
        if getattr(gap, "status", "open") == "resolved":
            continue
        if text := _safe_text(getattr(gap, "description", None)):
            lines.append(f"- 尚待验证：{text}")

    if not lines:
        lines.append("- 当前未记录明确风险；未覆盖事项仍应视为未知，而非已满足。")

    return lines


def _reversal_projection(state: SummaryState) -> list[str]:
    decision = state.decision_case
    assert decision is not None

    lines: list[str] = []
    for trigger in state.decision_reevaluation_triggers:
        for rationale in getattr(trigger, "rationale", []) or []:
            if text := _safe_text(rationale):
                lines.append(f"- {text}")

    if lines:
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


def _known_candidate_names(
    candidate_ids: object,
    candidate_names: dict[str, str],
) -> list[str]:
    if not isinstance(candidate_ids, (list, tuple)):
        return []

    return [
        candidate_names[candidate_id]
        for candidate_id in candidate_ids
        if candidate_id in candidate_names
    ]


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
