"""Explainable decision-impact decomposition for research gaps."""

from __future__ import annotations

from dataclasses import asdict

from models import (
    DecisionCase,
    DecisionComparison,
    DecisionEvaluation,
    ExpectedDecisionImpact,
    IntegrationAssessment,
    RecommendationRobustness,
    ResearchAnalysis,
    ResearchGap,
    SensitivityResult,
    TechnicalContext,
)


IMPACT_LEVEL = {
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


def decompose_expected_decision_impact(
    decision: DecisionCase,
    analysis: ResearchAnalysis,
    comparison: DecisionComparison,
    evaluation: DecisionEvaluation,
    sensitivity: list[SensitivityResult],
    robustness: RecommendationRobustness | None,
    technical_context: TechnicalContext | None,
    integration_assessments: list[IntegrationAssessment],
) -> ResearchAnalysis:
    """
    Attach deterministic impact dimensions to every existing ResearchGap.

    This service does not modify gap priority, severity, candidate ranking,
    or the recommendation itself.
    """

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

    unresolved_ids = set(
        evaluation.unresolved_candidate_ids
    )

    architecture_status = (
        _architecture_status_by_candidate(
            decision,
            technical_context,
            integration_assessments,
        )
    )

    for gap in analysis.research_gaps:
        gap.expected_decision_impact = (
            _decompose_gap(
                decision_id=decision.decision_id,
                gap=gap,
                winner_id=winner_id,
                challenger_ids=challenger_ids,
                flip_criteria=flip_criteria,
                near_flip_criteria=near_flip_criteria,
                unresolved_ids=unresolved_ids,
                architecture_status=architecture_status,
                robustness=robustness,
            )
        )

    return analysis


def _decompose_gap(
    *,
    decision_id: str,
    gap: ResearchGap,
    winner_id: str | None,
    challenger_ids: set[str],
    flip_criteria: set[str],
    near_flip_criteria: set[str],
    unresolved_ids: set[str],
    architecture_status: dict[str, str],
    robustness: RecommendationRobustness | None,
) -> ExpectedDecisionImpact:
    drivers: list[str] = []

    ranking = _ranking_impact(
        gap,
        winner_id=winner_id,
        challenger_ids=challenger_ids,
        flip_criteria=flip_criteria,
        near_flip_criteria=near_flip_criteria,
        drivers=drivers,
    )

    constraint = _constraint_impact(
        gap,
        unresolved_ids=unresolved_ids,
        drivers=drivers,
    )

    architecture = _architecture_impact(
        gap,
        architecture_status=architecture_status,
        drivers=drivers,
    )

    conflict = _conflict_impact(
        gap,
        winner_id=winner_id,
        challenger_ids=challenger_ids,
        flip_criteria=flip_criteria,
        drivers=drivers,
    )

    readiness = _readiness_impact(
        gap,
        winner_id=winner_id,
        challenger_ids=challenger_ids,
        near_flip_criteria=near_flip_criteria,
        unresolved_ids=unresolved_ids,
        drivers=drivers,
    )

    robustness_impact = _robustness_impact(
        gap,
        winner_id=winner_id,
        challenger_ids=challenger_ids,
        flip_criteria=flip_criteria,
        near_flip_criteria=near_flip_criteria,
        robustness=robustness,
        drivers=drivers,
    )

    if winner_id is None:
        overall = "UNKNOWN"
    else:
        overall = _max_known_impact(
            ranking,
            constraint,
            architecture,
            conflict,
            readiness,
            robustness_impact,
        )

        # Preserve 17.5 as the authoritative routing decision.
        # Phase 18 may explain it but must not silently downgrade it.
        if (
            gap.decision_impact in IMPACT_LEVEL
            and IMPACT_LEVEL[gap.decision_impact]
            > IMPACT_LEVEL.get(overall, 0)
        ):
            overall = gap.decision_impact

    return ExpectedDecisionImpact(
        decision_id=decision_id,
        gap_id=gap.gap_id,
        overall_impact=overall,
        ranking_impact=ranking,
        constraint_impact=constraint,
        architecture_impact=architecture,
        conflict_resolution_impact=conflict,
        readiness_impact=readiness,
        robustness_impact=robustness_impact,
        drivers=_dedupe(drivers),
    )


def _ranking_impact(
    gap: ResearchGap,
    *,
    winner_id: str | None,
    challenger_ids: set[str],
    flip_criteria: set[str],
    near_flip_criteria: set[str],
    drivers: list[str],
) -> str:
    if winner_id is None:
        return "UNKNOWN"

    if gap.criterion_id in near_flip_criteria:
        drivers.append(
            "Gap affects a criterion with a near recommendation switch."
        )
        return "HIGH"

    if (
        gap.criterion_id in flip_criteria
        and (
            gap.candidate_id == winner_id
            or gap.candidate_id in challenger_ids
        )
    ):
        drivers.append(
            "Gap affects the winner or a direct challenger on a "
            "recommendation-sensitive criterion."
        )
        return "HIGH"

    if (
        gap.criterion_id in flip_criteria
        or gap.candidate_id == winner_id
        or gap.candidate_id in challenger_ids
    ):
        drivers.append(
            "Gap is connected to the current ranking."
        )
        return "MEDIUM"

    return "LOW"


def _constraint_impact(
    gap: ResearchGap,
    *,
    unresolved_ids: set[str],
    drivers: list[str],
) -> str:
    if gap.candidate_id in unresolved_ids:
        drivers.append(
            "Resolving this candidate's uncertainty may clarify "
            "hard-constraint eligibility."
        )
        return "HIGH"

    return "LOW"


def _architecture_impact(
    gap: ResearchGap,
    *,
    architecture_status: dict[str, str],
    drivers: list[str],
) -> str:
    status = architecture_status.get(
        gap.candidate_id,
        "UNKNOWN",
    )

    if status == "UNKNOWN":
        return "UNKNOWN"

    if status == "INCOMPLETE":
        drivers.append(
            "Architecture fit for this candidate is incomplete."
        )
        return "MEDIUM"

    return "LOW"


def _conflict_impact(
    gap: ResearchGap,
    *,
    winner_id: str | None,
    challenger_ids: set[str],
    flip_criteria: set[str],
    drivers: list[str],
) -> str:
    if gap.gap_type != "conflicting_evidence":
        return "LOW"

    if winner_id is None:
        return "UNKNOWN"

    if (
        gap.candidate_id == winner_id
        or gap.candidate_id in challenger_ids
        or gap.criterion_id in flip_criteria
    ):
        drivers.append(
            "Resolving conflicting evidence may materially affect "
            "a decision-relevant candidate or criterion."
        )
        return "HIGH"

    drivers.append(
        "Resolving this evidence conflict can improve decision consistency."
    )
    return "MEDIUM"


def _readiness_impact(
    gap: ResearchGap,
    *,
    winner_id: str | None,
    challenger_ids: set[str],
    near_flip_criteria: set[str],
    unresolved_ids: set[str],
    drivers: list[str],
) -> str:
    if winner_id is None:
        return "UNKNOWN"

    if (
        gap.candidate_id in unresolved_ids
        or gap.criterion_id in near_flip_criteria
    ):
        drivers.append(
            "Resolving this gap may remove a major source of decision "
            "readiness uncertainty."
        )
        return "HIGH"

    if (
        gap.candidate_id == winner_id
        or gap.candidate_id in challenger_ids
        or gap.gap_type
        in {
            "missing_evidence",
            "low_coverage",
            "weak_source",
            "conflicting_evidence",
        }
    ):
        return "MEDIUM"

    return "LOW"


def _robustness_impact(
    gap: ResearchGap,
    *,
    winner_id: str | None,
    challenger_ids: set[str],
    flip_criteria: set[str],
    near_flip_criteria: set[str],
    robustness: RecommendationRobustness | None,
    drivers: list[str],
) -> str:
    if robustness is None:
        return "UNKNOWN"

    if winner_id is None:
        return "UNKNOWN"

    relevant = (
        gap.candidate_id == winner_id
        or gap.candidate_id in challenger_ids
        or gap.criterion_id in flip_criteria
    )

    if (
        robustness.status == "FRAGILE"
        and (
            relevant
            or gap.criterion_id in near_flip_criteria
        )
    ):
        drivers.append(
            "Resolving this gap may strengthen a fragile recommendation."
        )
        return "HIGH"

    if (
        robustness.status == "MODERATE"
        and relevant
    ):
        drivers.append(
            "Resolving this gap may improve recommendation robustness."
        )
        return "MEDIUM"

    if robustness.status == "ROBUST":
        return "LOW"

    return "UNKNOWN"


def _architecture_status_by_candidate(
    decision: DecisionCase,
    technical_context: TechnicalContext | None,
    assessments: list[IntegrationAssessment],
) -> dict[str, str]:
    if not _context_has_information(
        technical_context
    ):
        return {
            candidate.candidate_id: "UNKNOWN"
            for candidate in decision.candidates
        }

    by_candidate = {
        item.candidate_id: item
        for item in assessments
        if item.decision_id == decision.decision_id
    }

    result: dict[str, str] = {}

    for candidate in decision.candidates:
        assessment = by_candidate.get(
            candidate.candidate_id
        )

        if assessment is None:
            result[candidate.candidate_id] = (
                "INCOMPLETE"
            )
            continue

        if any(
            getattr(
                assessment,
                field_name,
                "UNKNOWN",
            ) == "UNKNOWN"
            for field_name in ARCHITECTURE_FIELDS
        ):
            result[candidate.candidate_id] = (
                "INCOMPLETE"
            )
        else:
            result[candidate.candidate_id] = (
                "COMPLETE"
            )

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


def _max_known_impact(
    *values: str,
) -> str:
    known = [
        value
        for value in values
        if value != "UNKNOWN"
    ]

    if not known:
        return "UNKNOWN"

    return max(
        known,
        key=lambda value: IMPACT_LEVEL[value],
    )


def _dedupe(
    values: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result
