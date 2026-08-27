"""Deterministic planning for technical decision re-evaluation."""

from __future__ import annotations

from models import (
    DecisionCase,
    DecisionReevaluationTrigger,
    ReevaluationAssessment,
    ReevaluationPlan,
)


def build_reevaluation_plan(
    decision: DecisionCase,
    assessment: ReevaluationAssessment,
    triggers: list[DecisionReevaluationTrigger],
) -> ReevaluationPlan:
    """
    Convert a deterministic re-evaluation assessment into a bounded plan.

    The plan describes what must be revisited.

    It never:
    - executes research;
    - creates candidate scores;
    - predicts a winner;
    - changes recommendation;
    - calls an LLM;
    - mutates ResearchAnalysis or ResearchGap;
    """

    if assessment.decision_id != decision.decision_id:
        raise ValueError(
            "assessment decision_id does not match decision"
        )

    relevant = {
        trigger.trigger_id: trigger
        for trigger in triggers
        if trigger.decision_id == decision.decision_id
    }

    matched = [
        relevant[trigger_id]
        for trigger_id in assessment.matched_trigger_ids
        if trigger_id in relevant
    ]

    candidate_names = {
        candidate.candidate_id: candidate.name
        for candidate in decision.candidates
    }

    criterion_names = {
        criterion.criterion_id: criterion.name
        for criterion in decision.criteria
    }

    plan = ReevaluationPlan(
        decision_id=decision.decision_id,
        status=assessment.status,
        matched_trigger_ids=list(
            assessment.matched_trigger_ids
        ),
        modules_to_recompute=_sorted_unique(
            assessment.invalidated_modules
        ),
        candidate_ids_to_recheck=_sorted_unique(
            assessment.affected_candidate_ids
        ),
        criterion_ids_to_recheck=_sorted_unique(
            assessment.affected_criterion_ids
        ),
        scenario_ids_to_recheck=_sorted_unique(
            assessment.affected_scenario_ids
        ),
        reasons=list(
            assessment.reasons
        ),
    )

    if assessment.status in {
        "NOT_REQUIRED",
        "UNKNOWN",
    }:
        return plan

    plan.research_queries = _build_queries(
        matched,
        candidate_names,
        criterion_names,
    )

    return plan


def _build_queries(
    triggers: list[DecisionReevaluationTrigger],
    candidate_names: dict[str, str],
    criterion_names: dict[str, str],
) -> list[str]:
    queries: list[str] = []

    for trigger in triggers:
        candidates = [
            candidate_names.get(
                candidate_id,
                candidate_id,
            )
            for candidate_id in (
                trigger.affected_candidate_ids
                or []
            )
        ]

        criteria = [
            criterion_names.get(
                criterion_id,
                criterion_id,
            )
            for criterion_id in (
                trigger.affected_criterion_ids
                or []
            )
        ]

        base_terms: list[str] = []

        if candidates:
            base_terms.append(
                " ".join(candidates)
            )

        if criteria:
            base_terms.append(
                " ".join(criteria)
            )

        if trigger.source_field:
            base_terms.append(
                trigger.source_field.replace(
                    "_",
                    " ",
                )
            )

        if trigger.trigger_type:
            base_terms.append(
                trigger.trigger_type.replace(
                    "_",
                    " ",
                ).lower()
            )

        base_terms.append(
            "updated evidence"
        )

        query = " ".join(
            term.strip()
            for term in base_terms
            if term and term.strip()
        )

        if query:
            queries.append(query)

    return _dedupe_preserve_order(
        queries
    )


def _sorted_unique(
    values: list[str],
) -> list[str]:
    return sorted(
        {
            str(value)
            for value in values
            if value
        }
    )


def _dedupe_preserve_order(
    values: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = " ".join(
            value.split()
        )

        key = normalized.casefold()

        if not normalized or key in seen:
            continue

        seen.add(key)
        result.append(normalized)

    return result
