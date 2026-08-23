"""Deterministic assumption analysis for technical decisions."""

from __future__ import annotations

from models import (
    DecisionAssumption,
    DecisionCase,
    IntegrationAssessment,
    RecommendationRobustness,
    SensitivityResult,
    TechnicalContext,
)


NEAR_FLIP_RELATIVE_DELTA = 0.10

CONTEXT_FIELDS = (
    "existing_stack",
    "deployment_environment",
    "infrastructure",
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

ARCHITECTURE_RELEVANT_FIELDS = {
    "existing_stack",
    "deployment_environment",
    "infrastructure",
    "team_capabilities",
    "integration_requirements",
    "operational_constraints",
    "migration_constraints",
}

FIELD_LABELS = {
    "existing_stack": "Existing stack",
    "deployment_environment": "Deployment environment",
    "infrastructure": "Infrastructure",
    "team_capabilities": "Team capabilities",
    "scale_requirements": "Scale requirements",
    "performance_requirements": "Performance requirements",
    "reliability_requirements": "Reliability requirements",
    "integration_requirements": "Integration requirements",
    "operational_constraints": "Operational constraints",
    "security_constraints": "Security constraints",
    "compliance_constraints": "Compliance constraints",
    "migration_constraints": "Migration constraints",
    "budget_constraints": "Budget constraints",
}


def analyze_decision_assumptions(
    decision: DecisionCase,
    technical_context: TechnicalContext | None,
    sensitivity: list[SensitivityResult],
    robustness: RecommendationRobustness | None,
    integration_assessments: list[IntegrationAssessment],
) -> list[DecisionAssumption]:
    """
    Build an explicit inventory of assumptions already embedded in the
    current decision state.

    No new facts are inferred and no LLM is called.
    """

    assumptions: list[DecisionAssumption] = []

    assumptions.extend(
        _context_assumptions(
            decision,
            technical_context,
            robustness,
            integration_assessments,
        )
    )

    assumptions.extend(
        _criterion_weight_assumptions(
            decision,
            sensitivity,
        )
    )

    return sorted(
        assumptions,
        key=lambda item: (
            -_impact_rank(item.decision_impact),
            item.assumption_type,
            item.source_field or "",
            item.source_value or "",
            item.assumption_id,
        ),
    )


def _context_assumptions(
    decision: DecisionCase,
    context: TechnicalContext | None,
    robustness: RecommendationRobustness | None,
    integration_assessments: list[IntegrationAssessment],
) -> list[DecisionAssumption]:
    if context is None:
        return []

    candidate_ids = [
        candidate.candidate_id
        for candidate in decision.candidates
    ]

    architecture_incomplete = (
        _has_architecture_uncertainty(
            decision,
            integration_assessments,
        )
    )

    result: list[DecisionAssumption] = []

    for field_name in CONTEXT_FIELDS:
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

            impact = "LOW"
            sensitivity = "LOW"

            if field_name in ARCHITECTURE_RELEVANT_FIELDS:
                impact = "MEDIUM"
                sensitivity = "MEDIUM"

                if architecture_incomplete:
                    impact = "HIGH"

                if (
                    robustness is not None
                    and robustness.status == "FRAGILE"
                ):
                    sensitivity = "HIGH"

            result.append(
                DecisionAssumption(
                    decision_id=decision.decision_id,
                    text=(
                        f"{FIELD_LABELS[field_name]} remains "
                        f"consistent with: {value}."
                    ),
                    assumption_type="CONTEXT",
                    source_type="technical_context",
                    source_field=field_name,
                    source_value=value,
                    affected_candidate_ids=list(
                        candidate_ids
                    ),
                    change_sensitivity=sensitivity,
                    decision_impact=impact,
                    rationale=(
                        "Current architecture and applicability "
                        "assessments are evaluated under this "
                        "explicit technical context."
                    ),
                )
            )

    return result


def _criterion_weight_assumptions(
    decision: DecisionCase,
    sensitivity: list[SensitivityResult],
) -> list[DecisionAssumption]:
    total_weight = sum(
        criterion.weight
        for criterion in decision.criteria
    )

    by_criterion = {
        item.criterion_id: item
        for item in sensitivity
        if item.decision_id == decision.decision_id
    }

    result: list[DecisionAssumption] = []

    for criterion in decision.criteria:
        sensitivity_result = by_criterion.get(
            criterion.criterion_id
        )

        impact = "LOW"
        change_sensitivity = "LOW"
        rationale = (
            "The current recommendation uses this criterion "
            "weight as supplied."
        )

        if (
            sensitivity_result is not None
            and sensitivity_result.recommendation_changes
        ):
            impact = "MEDIUM"
            change_sensitivity = "MEDIUM"

            if (
                sensitivity_result.weight_delta is not None
                and total_weight > 0
                and (
                    abs(sensitivity_result.weight_delta)
                    / total_weight
                    <= NEAR_FLIP_RELATIVE_DELTA
                )
            ):
                impact = "HIGH"
                change_sensitivity = "HIGH"
                rationale = (
                    "A small change in this criterion weight "
                    "can change the recommended candidate."
                )
            else:
                rationale = (
                    "A tested change in this criterion weight "
                    "can change the recommended candidate."
                )

        result.append(
            DecisionAssumption(
                decision_id=decision.decision_id,
                text=(
                    f"The relative importance of "
                    f"{criterion.name} remains at its "
                    f"current weight ({criterion.weight})."
                ),
                assumption_type="PRIORITY",
                source_type="decision_criterion",
                source_field="weight",
                source_value=str(
                    criterion.weight
                ),
                affected_candidate_ids=[
                    candidate.candidate_id
                    for candidate in decision.candidates
                ],
                affected_criterion_ids=[
                    criterion.criterion_id
                ],
                change_sensitivity=change_sensitivity,
                decision_impact=impact,
                rationale=rationale,
            )
        )

    return result


def _has_architecture_uncertainty(
    decision: DecisionCase,
    assessments: list[IntegrationAssessment],
) -> bool:
    core_fields = (
        "integration_complexity",
        "migration_complexity",
        "operational_change",
        "infrastructure_change",
    )

    by_candidate = {
        item.candidate_id: item
        for item in assessments
        if item.decision_id == decision.decision_id
    }

    for candidate in decision.candidates:
        assessment = by_candidate.get(
            candidate.candidate_id
        )

        if assessment is None:
            return True

        if any(
            getattr(
                assessment,
                field_name,
                "UNKNOWN",
            ) == "UNKNOWN"
            for field_name in core_fields
        ):
            return True

    return False


def _impact_rank(
    value: str,
) -> int:
    return {
        "UNKNOWN": 0,
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
    }.get(value, 0)
