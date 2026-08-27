"""Bridge deterministic re-evaluation plans into existing research gaps."""

from __future__ import annotations

import hashlib

from models import (
    DecisionCase,
    ReevaluationPlan,
    ResearchGap,
)
from services.search_strategy import (
    assign_search_strategies,
)


ACTIONABLE_REEVALUATION_STATUSES = {
    "REQUIRED",
    "RECOMMENDED",
}


def build_reevaluation_research_gaps(
    decision: DecisionCase,
    plan: ReevaluationPlan,
) -> list[ResearchGap]:
    """
    Convert an actionable re-evaluation plan into ordinary open ResearchGap
    objects that can be consumed by the existing adaptive research planner.

    This bridge never:
    - creates TodoItem objects;
    - performs retrieval;
    - changes adaptive lifecycle state;
    - changes stopping decisions;
    - creates candidate scores;
    - predicts a winner;
    - changes recommendations;
    - invents candidate × criterion pair relationships.
    """

    if plan.decision_id != decision.decision_id:
        raise ValueError(
            "reevaluation plan decision_id does not match decision"
        )

    if plan.status not in ACTIONABLE_REEVALUATION_STATUSES:
        return []

    queries = _dedupe_queries(
        plan.research_queries
    )

    if not queries:
        return []

    valid_candidate_ids = {
        candidate.candidate_id
        for candidate in decision.candidates
    }

    valid_criterion_ids = {
        criterion.criterion_id
        for criterion in decision.criteria
    }

    candidate_ids = [
        candidate_id
        for candidate_id in plan.candidate_ids_to_recheck
        if candidate_id in valid_candidate_ids
    ]

    criterion_ids = [
        criterion_id
        for criterion_id in plan.criterion_ids_to_recheck
        if criterion_id in valid_criterion_ids
    ]

    # Preserve an exact scope only when the plan identifies one unique
    # candidate / criterion. Multiple IDs are intentionally NOT expanded
    # into synthetic candidate × criterion relationships.
    candidate_id = (
        candidate_ids[0]
        if len(set(candidate_ids)) == 1
        else ""
    )

    criterion_id = (
        criterion_ids[0]
        if len(set(criterion_ids)) == 1
        else ""
    )

    priority, severity = _routing_priority(
        plan.status
    )

    gaps: list[ResearchGap] = []

    for query in queries:
        gap = ResearchGap(
            gap_id=_gap_id(
                decision.decision_id,
                query,
            ),
            candidate_id=candidate_id,
            criterion_id=criterion_id,
            gap_type="reevaluation",
            severity=severity,
            description=(
                "Re-evaluate potentially stale decision state "
                f"using updated evidence: {query}"
            ),
            suggested_query=query,
            status="open",
        )

        # Routing priority is orchestration metadata only.
        # It is not candidate quality or decision impact.
        gap.priority = priority

        # Give search strategy deterministic contextual hints without
        # asserting new technical facts.
        gap.context_dimensions = _context_dimensions(
            plan
        )

        gaps.append(gap)

    # Reuse Phase25 strategy assignment. This only enriches retrieval
    # intent fields and must not change decision truth.
    assign_search_strategies(
        decision,
        gaps,
    )

    return gaps


def _routing_priority(
    status: str,
) -> tuple[int, float]:
    if status == "REQUIRED":
        return 3, 1.0

    if status == "RECOMMENDED":
        return 2, 0.7

    return 0, 0.0


def _context_dimensions(
    plan: ReevaluationPlan,
) -> list[str]:
    values = [
        *plan.modules_to_recompute,
        *plan.reasons,
    ]

    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = " ".join(
            str(value).strip().split()
        )

        if not normalized:
            continue

        key = normalized.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(normalized)

    return result


def _dedupe_queries(
    values: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = " ".join(
            str(value).strip().split()
        )

        if not normalized:
            continue

        key = normalized.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(normalized)

    return result


def _gap_id(
    decision_id: str,
    query: str,
) -> str:
    payload = (
        f"{decision_id}\n{query.casefold()}"
    ).encode("utf-8")

    digest = hashlib.sha256(
        payload
    ).hexdigest()[:12]

    return f"gap_reeval_{digest}"
