"""Deterministic reporting policy for decision-aware final reports."""

from __future__ import annotations

from models import SummaryState


DEFINITIVE_READY_STATUSES = {
    "READY",
}


def build_decision_reporting_context(
    state: SummaryState,
) -> str:
    """
    Build deterministic instructions that constrain final-report language.

    The reporting LLM does not decide whether a recommendation is ready.
    It receives the persisted deterministic decision-intelligence state and
    must write within that policy.

    Non-decision or unavailable decision-intelligence state returns an empty
    string so normal research reporting remains unchanged.
    """

    decision = state.decision_case
    readiness = state.decision_readiness

    if decision is None or readiness is None:
        return ""

    readiness_status = str(
        readiness.status or "UNKNOWN"
    ).upper()

    recommendation = (
        decision.recommendation.strip()
        if isinstance(
            decision.recommendation,
            str,
        )
        and decision.recommendation.strip()
        else None
    )

    definitive_allowed = (
        readiness_status
        in DEFINITIVE_READY_STATUSES
        and recommendation is not None
    )

    stopping = state.stopping_decision
    analysis = state.research_analysis

    stopping_reason = (
        stopping.reason
        if stopping is not None
        else "unavailable"
    )

    actionable_gap_count = (
        stopping.actionable_gap_count
        if stopping is not None
        else len(
            getattr(
                analysis,
                "research_gaps",
                [],
            )
            or []
        )
    )

    blocking_reasons = list(
        readiness.blocking_reasons or []
    )

    if definitive_allowed:
        policy_lines = [
            "REPORTING POLICY: DEFINITIVE_RECOMMENDATION_ALLOWED",
            (
                "The deterministic decision-readiness state is READY "
                "and a structured recommendation is present. "
                "A definitive recommendation is permitted, but only when "
                "grounded in the supplied evidence."
            ),
            (
                "Do not exaggerate certainty beyond the evidence, and "
                "preserve any remaining caveats or limitations."
            ),
        ]
    else:
        policy_lines = [
            "REPORTING POLICY: PROVISIONAL_ONLY",
            (
                "The deterministic decision-readiness state does NOT allow "
                "a definitive production recommendation."
            ),
            (
                "Do not describe any candidate as conclusively best, the "
                "clear winner, the required choice, or the definitive "
                "production selection."
            ),
            (
                "Do not present a definitive recommendation order such as "
                "'A > B > C' as the final decision."
            ),
            (
                "You may describe the current evidence as leaning toward a "
                "candidate on specific criteria, but clearly label this as "
                "provisional."
            ),
            (
                "Explicitly distinguish current evidence direction from "
                "decision readiness."
            ),
            (
                "Explain unresolved blockers and recommend additional "
                "validation, benchmarking, PoC work, or research where "
                "appropriate."
            ),
            (
                "Budget exhaustion means only that the configured research "
                "budget ended. It does NOT mean the decision is ready."
            ),
        ]

    lines = [
        "=== DETERMINISTIC DECISION INTELLIGENCE CONTEXT ===",
        f"Decision question: {decision.question}",
        f"Readiness status: {readiness_status}",
        (
            "Structured recommendation: PRESENT"
            if recommendation is not None
            else "Structured recommendation: MISSING"
        ),
        f"Readiness score: {readiness.overall_score:.3f}",
        f"Criterion coverage: {readiness.criterion_coverage:.3f}",
        f"Evidence quality: {readiness.evidence_quality:.3f}",
        f"Applicability: {readiness.applicability:.3f}",
        f"Agreement score: {readiness.agreement_score:.3f}",
        f"Decision margin: {readiness.decision_margin:.3f}",
        f"Stopping reason: {stopping_reason}",
        f"Actionable research gaps: {actionable_gap_count}",
    ]

    if blocking_reasons:
        lines.append("Blocking reasons:")
        lines.extend(
            f"- {reason}"
            for reason in blocking_reasons
        )
    else:
        lines.append("Blocking reasons: none reported")

    lines.extend(policy_lines)

    lines.extend(
        [
            (
                "The deterministic state above is authoritative for "
                "recommendation certainty."
            ),
            (
                "Do not override or reinterpret its readiness status."
            ),
            "=== END DECISION INTELLIGENCE CONTEXT ===",
        ]
    )

    return "\n".join(lines)
