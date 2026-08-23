"""Decision-impact enrichment for adaptive research gaps."""

from __future__ import annotations

from dataclasses import asdict

from models import (
    DecisionCase,
    DecisionComparison,
    DecisionEvaluation,
    IntegrationAssessment,
    RecommendationRobustness,
    ResearchAnalysis,
    ResearchGap,
    SensitivityResult,
    TechnicalContext,
)


IMPACT_PRIORITY = {
    "UNKNOWN": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}

NEAR_FLIP_RELATIVE_DELTA = 0.10

ARCHITECTURE_FIELDS = (
    "integration_complexity",
    "migration_complexity",
    "operational_change",
    "infrastructure_change",
)

CONTEXT_QUERY_FIELDS = (
    "deployment_environment",
    "infrastructure",
    "existing_stack",
    "team_capabilities",
    "scale_requirements",
    "performance_requirements",
    "reliability_requirements",
    "integration_requirements",
    "operational_constraints",
    "security_constraints",
    "compliance_constraints",
    "migration_constraints",
    "budget_constraints",
)


def enrich_research_gaps_with_decision_impact(
    decision: DecisionCase,
    analysis: ResearchAnalysis,
    comparison: DecisionComparison,
    evaluation: DecisionEvaluation,
    sensitivity: list[SensitivityResult],
    robustness: RecommendationRobustness | None,
    technical_context: TechnicalContext | None,
    integration_assessments: list[IntegrationAssessment],
) -> ResearchAnalysis:
    """Add deterministic decision-impact metadata to existing gaps."""

    if analysis.decision_id != decision.decision_id:
        raise ValueError(
            "research analysis does not belong to supplied decision"
        )

    winner_id = _winner_id(
        decision,
        comparison,
    )

    total_weight = sum(
        criterion.weight
        for criterion in decision.criteria
    )

    relevant_sensitivity = [
        item
        for item in sensitivity
        if (
            item.decision_id == decision.decision_id
            and (
                winner_id is None
                or item.baseline_winner_id == winner_id
            )
        )
    ]

    flip_criteria = {
        item.criterion_id
        for item in relevant_sensitivity
        if item.recommendation_changes
    }

    near_flip_criteria = {
        item.criterion_id
        for item in relevant_sensitivity
        if (
            item.recommendation_changes
            and item.weight_delta is not None
            and total_weight > 0
            and abs(item.weight_delta) / total_weight
            <= NEAR_FLIP_RELATIVE_DELTA
        )
    }

    challenger_ids = {
        item.competing_candidate_id
        for item in relevant_sensitivity
        if (
            item.recommendation_changes
            and item.competing_candidate_id
        )
    }

    unresolved_candidate_ids = set(
        evaluation.unresolved_candidate_ids
    )

    architecture_unknown_ids = (
        _architecture_unknown_candidate_ids(
            decision,
            technical_context,
            integration_assessments,
        )
    )

    context_terms = _context_terms(
        technical_context
    )

    for gap in analysis.research_gaps:
        impact, reasons = _classify_gap_impact(
            gap=gap,
            winner_id=winner_id,
            flip_criteria=flip_criteria,
            near_flip_criteria=near_flip_criteria,
            challenger_ids=challenger_ids,
            unresolved_candidate_ids=unresolved_candidate_ids,
            architecture_unknown_ids=architecture_unknown_ids,
            robustness=robustness,
        )

        gap.decision_impact = impact
        gap.priority = IMPACT_PRIORITY[impact]
        gap.impact_reasons = reasons

        (
            gap.suggested_query,
            gap.context_dimensions,
        ) = _contextualize_query(
            gap.suggested_query,
            context_terms,
        )

    analysis.research_gaps.sort(
        key=lambda gap: (
            -gap.priority,
            -gap.severity,
            gap.candidate_id,
            gap.criterion_id,
            gap.gap_type,
            gap.gap_id,
        )
    )

    return analysis


def _winner_id(
    decision: DecisionCase,
    comparison: DecisionComparison,
) -> str | None:
    if comparison.decision_id != decision.decision_id:
        return None

    if comparison.status != "complete":
        return None

    if not comparison.ranked_candidate_ids:
        return None

    return comparison.ranked_candidate_ids[0]


def _classify_gap_impact(
    *,
    gap: ResearchGap,
    winner_id: str | None,
    flip_criteria: set[str],
    near_flip_criteria: set[str],
    challenger_ids: set[str],
    unresolved_candidate_ids: set[str],
    architecture_unknown_ids: set[str],
    robustness: RecommendationRobustness | None,
) -> tuple[str, list[str]]:
    if winner_id is None:
        return (
            "UNKNOWN",
            [
                "Decision impact cannot be ranked because "
                "the current comparison has no stable winner."
            ],
        )

    high_reasons: list[str] = []

    if gap.candidate_id in unresolved_candidate_ids:
        high_reasons.append(
            "This candidate still has unresolved hard constraints."
        )

    if gap.criterion_id in near_flip_criteria:
        high_reasons.append(
            "This criterion can change the recommendation under "
            "a small weight perturbation."
        )

    if (
        gap.candidate_id == winner_id
        and gap.criterion_id in flip_criteria
    ):
        high_reasons.append(
            "The gap affects the current winner on a "
            "recommendation-sensitive criterion."
        )

    if (
        gap.candidate_id in challenger_ids
        and gap.criterion_id in flip_criteria
    ):
        high_reasons.append(
            "The gap affects a direct competing candidate on a "
            "recommendation-sensitive criterion."
        )

    if high_reasons:
        return "HIGH", _dedupe(high_reasons)

    moderate_reasons: list[str] = []

    if gap.criterion_id in flip_criteria:
        moderate_reasons.append(
            "The gap concerns a criterion that can change the winner."
        )

    if gap.candidate_id == winner_id:
        moderate_reasons.append(
            "The gap directly affects the current leading candidate."
        )

    if gap.candidate_id in challenger_ids:
        moderate_reasons.append(
            "The gap affects a candidate that can replace the current winner."
        )

    if gap.candidate_id in architecture_unknown_ids:
        moderate_reasons.append(
            "Architecture fit for this candidate remains incomplete."
        )

    if (
        gap.gap_type == "conflicting_evidence"
        and (
            gap.candidate_id == winner_id
            or gap.candidate_id in challenger_ids
        )
    ):
        moderate_reasons.append(
            "Conflicting evidence affects a decision-relevant candidate."
        )

    if (
        robustness is not None
        and robustness.status == "FRAGILE"
        and gap.candidate_id == winner_id
    ):
        moderate_reasons.append(
            "The current recommendation is fragile, increasing the "
            "value of resolving uncertainty about the winner."
        )

    if moderate_reasons:
        return "MEDIUM", _dedupe(moderate_reasons)

    return (
        "LOW",
        [
            "This gap is currently less connected to the winner, "
            "direct challengers, or recommendation-sensitive criteria."
        ],
    )


def _architecture_unknown_candidate_ids(
    decision: DecisionCase,
    technical_context: TechnicalContext | None,
    assessments: list[IntegrationAssessment],
) -> set[str]:
    if not _context_has_information(
        technical_context
    ):
        return set()

    by_candidate = {
        item.candidate_id: item
        for item in assessments
        if item.decision_id == decision.decision_id
    }

    result: set[str] = set()

    for candidate in decision.candidates:
        assessment = by_candidate.get(
            candidate.candidate_id
        )

        if assessment is None:
            result.add(candidate.candidate_id)
            continue

        if any(
            getattr(
                assessment,
                field_name,
                "UNKNOWN",
            ) == "UNKNOWN"
            for field_name in ARCHITECTURE_FIELDS
        ):
            result.add(candidate.candidate_id)

    return result


def _context_has_information(
    context: TechnicalContext | None,
) -> bool:
    if context is None:
        return False

    return any(
        bool(value)
        for value in asdict(context).values()
    )


def _context_terms(
    context: TechnicalContext | None,
) -> list[tuple[str, str]]:
    if context is None:
        return []

    result: list[tuple[str, str]] = []
    seen: set[str] = set()

    for field_name in CONTEXT_QUERY_FIELDS:
        values = getattr(
            context,
            field_name,
            [],
        )

        for raw_value in values:
            value = " ".join(
                str(raw_value).strip().split()
            )

            if not value:
                continue

            value = value[:80]
            key = value.casefold()

            if key in seen:
                continue

            seen.add(key)
            result.append(
                (field_name, value)
            )

            if len(result) >= 4:
                return result

    return result


def _contextualize_query(
    query: str | None,
    context_terms: list[tuple[str, str]],
) -> tuple[str | None, list[str]]:
    if not query:
        return query, []

    if not context_terms:
        return query, []

    result = query.strip()
    normalized = result.casefold()
    dimensions: list[str] = []

    for dimension, value in context_terms:
        if value.casefold() not in normalized:
            result += f" {value}"
            normalized = result.casefold()

        dimensions.append(dimension)

    return result, _dedupe(dimensions)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result
