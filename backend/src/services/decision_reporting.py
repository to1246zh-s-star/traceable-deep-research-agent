"""Deterministic reporting policy for decision-aware final reports."""

from __future__ import annotations

import json
from dataclasses import asdict

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

    if decision is None:
        return ""

    readiness_status = str(
        (readiness.status if readiness is not None else "UNKNOWN")
        or "UNKNOWN"
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
        (readiness.blocking_reasons if readiness is not None else [])
        or []
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
        "=== AUTHORITATIVE STRUCTURED DECISION STATE ===",
        "SOURCE-OF-TRUTH RULES:",
        "- This structured decision state is authoritative.",
        (
            "- Task summaries, notes, and source summaries are "
            "NON-AUTHORITATIVE RESEARCH NARRATIVE only."
        ),
        (
            "- If narrative conflicts with structured state, ignore the "
            "conflicting narrative statement."
        ),
        "- Never contradict a structured constraint or claim status.",
        (
            "- UNKNOWN must remain UNKNOWN and be described as insufficient "
            "evidence or unresolved uncertainty."
        ),
        (
            "- Missing or weak evidence is not negative evidence and must "
            "not become unsupported, absent, failed, or unsatisfied."
        ),
        (
            "- SATISFIED may be stated as satisfied; UNSATISFIED may be "
            "stated as unsatisfied."
        ),
        (
            "- USER_PROVIDED_CONTEXT may be stated as context fact. Derived "
            "judgments must be labeled as inference and not invent effects."
        ),
        f"Decision question: {decision.question}",
        "Candidates: " + _json([asdict(item) for item in decision.candidates]),
        "Criteria: " + _json([asdict(item) for item in decision.criteria]),
        "Hard constraints (canonical status): " + _json(
            _canonical_constraint_statuses(state)
        ),
        "Decision evaluation: " + _json(
            asdict(state.decision_evaluation)
            if state.decision_evaluation is not None
            else None
        ),
        "USER_PROVIDED_CONTEXT: " + _json(
            asdict(state.technical_context)
            if state.technical_context is not None
            else None
        ),
        "Candidate criterion assessments: " + _json(
            asdict(state.decision_comparison)
            if state.decision_comparison is not None
            else None
        ),
        "Structured claims: " + _json(
            {
                "claims": [asdict(item) for item in state.claims],
                "atomic_claims": [asdict(item) for item in state.atomic_claims],
            }
        ),
        "Structured evidence: " + _json(
            {
                "evidence": [asdict(item) for item in state.evidence_items],
                "assessments": [
                    asdict(item) for item in state.evidence_assessments
                ],
            }
        ),
        "Unresolved research gaps: " + _json(
            [
                asdict(item)
                for item in getattr(analysis, "research_gaps", [])
                if item.status != "resolved"
            ]
        ),
        f"Readiness status: {readiness_status}",
        (
            "Structured recommendation: PRESENT"
            if recommendation is not None
            else "Structured recommendation: MISSING"
        ),
        "Structured recommendation value: " + _json(recommendation),
        "Recommendation robustness: " + _json(
            asdict(state.recommendation_robustness)
            if state.recommendation_robustness is not None
            else None
        ),
        "Readiness details: " + _json(
            asdict(readiness) if readiness is not None else None
        ),
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
            "=== END AUTHORITATIVE STRUCTURED DECISION STATE ===",
        ]
    )

    return "\n".join(lines)


def _canonical_constraint_statuses(
    state: SummaryState,
) -> list[dict[str, str]]:
    decision = state.decision_case
    if decision is None:
        return []

    evaluation = state.decision_evaluation
    results = {
        item.candidate_id: item
        for item in (
            evaluation.candidate_results
            if evaluation is not None
            else []
        )
    }
    rows: list[dict[str, str]] = []

    for candidate in decision.candidates:
        result = results.get(candidate.candidate_id)
        for constraint in decision.constraints:
            if (
                result is None
                or constraint.constraint_id in result.missing_constraint_ids
            ):
                status = "UNKNOWN"
            elif constraint.constraint_id in result.violated_constraint_ids:
                status = "UNSATISFIED"
            else:
                status = "SATISFIED"

            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "candidate_name": candidate.name,
                    "constraint_id": constraint.constraint_id,
                    "constraint": constraint.text,
                    "status": status,
                }
            )

    return rows


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
