"""Deterministic counterfactual analysis for technical decisions."""

from __future__ import annotations

from models import (
    DecisionAssumption,
    DecisionCase,
    DecisionCounterfactual,
    RecommendationRobustness,
)


IMPACT_RANK = {
    "UNKNOWN": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


CONTEXT_DIMENSIONS = {
    "existing_stack": [
        "architecture_fit",
        "integration",
        "migration",
    ],
    "deployment_environment": [
        "architecture_fit",
        "infrastructure",
        "integration",
        "operations",
    ],
    "infrastructure": [
        "architecture_fit",
        "infrastructure",
        "operations",
    ],
    "team_capabilities": [
        "integration",
        "migration",
        "operations",
    ],
    "scale_requirements": [
        "scalability",
        "architecture_fit",
        "infrastructure",
    ],
    "performance_requirements": [
        "performance",
        "architecture_fit",
    ],
    "reliability_requirements": [
        "reliability",
        "operations",
        "architecture_fit",
    ],
    "integration_requirements": [
        "integration",
        "architecture_fit",
    ],
    "operational_constraints": [
        "operations",
        "architecture_fit",
    ],
    "security_constraints": [
        "security",
        "architecture_fit",
    ],
    "compliance_constraints": [
        "compliance",
        "architecture_fit",
    ],
    "migration_constraints": [
        "migration",
        "integration",
        "architecture_fit",
    ],
    "budget_constraints": [
        "cost",
        "operations",
        "migration",
    ],
}


def analyze_decision_counterfactuals(
    decision: DecisionCase,
    assumptions: list[DecisionAssumption],
    robustness: RecommendationRobustness | None,
) -> list[DecisionCounterfactual]:
    """
    Derive bounded counterfactuals from explicit assumptions.

    Counterfactuals identify what must be reconsidered if an assumption
    changes. They do not synthesize new candidate scores or rankings.
    """

    result: list[DecisionCounterfactual] = []

    for assumption in assumptions:
        if assumption.decision_id != decision.decision_id:
            continue

        result.append(
            _from_assumption(
                decision,
                assumption,
                robustness,
            )
        )

    return sorted(
        result,
        key=lambda item: (
            -_impact_rank(
                item.recommendation_instability
            ),
            item.assumption_type,
            item.assumption_id,
            item.counterfactual_id,
        ),
    )


def _from_assumption(
    decision: DecisionCase,
    assumption: DecisionAssumption,
    robustness: RecommendationRobustness | None,
) -> DecisionCounterfactual:
    dimensions = _affected_dimensions(
        assumption
    )

    instability = _recommendation_instability(
        assumption,
        robustness,
    )

    reevaluation_required = (
        _reevaluation_required(
            assumption,
            instability,
        )
    )

    rationale = _rationale(
        assumption,
        dimensions,
        instability,
        robustness,
    )

    candidate_ids = [
        candidate_id
        for candidate_id
        in assumption.affected_candidate_ids
        if any(
            candidate.candidate_id == candidate_id
            for candidate in decision.candidates
        )
    ]

    criterion_ids = [
        criterion_id
        for criterion_id
        in assumption.affected_criterion_ids
        if any(
            criterion.criterion_id == criterion_id
            for criterion in decision.criteria
        )
    ]

    return DecisionCounterfactual(
        decision_id=decision.decision_id,
        assumption_id=assumption.assumption_id,
        statement=_statement(
            assumption
        ),
        assumption_type=assumption.assumption_type,
        source_field=assumption.source_field,
        source_value=assumption.source_value,
        affected_candidate_ids=_dedupe(
            candidate_ids
        ),
        affected_criterion_ids=_dedupe(
            criterion_ids
        ),
        affected_dimensions=dimensions,
        recommendation_instability=instability,
        reevaluation_required=reevaluation_required,
        rationale=rationale,
    )


def _statement(
    assumption: DecisionAssumption,
) -> str:
    base = assumption.text.strip()

    if base.endswith("."):
        base = base[:-1]

    return (
        "If this assumption no longer holds, "
        f"re-evaluate the decision: {base}."
    )


def _affected_dimensions(
    assumption: DecisionAssumption,
) -> list[str]:
    if assumption.assumption_type == "PRIORITY":
        return [
            "criterion_priority",
            "candidate_ranking",
            "recommendation_sensitivity",
        ]

    if assumption.assumption_type == "CONTEXT":
        if assumption.source_field is None:
            return [
                "architecture_fit",
                "integration",
            ]

        return list(
            CONTEXT_DIMENSIONS.get(
                assumption.source_field,
                [
                    "architecture_fit",
                    "integration",
                ],
            )
        )

    return []


def _recommendation_instability(
    assumption: DecisionAssumption,
    robustness: RecommendationRobustness | None,
) -> str:
    values = [
        assumption.decision_impact,
        assumption.change_sensitivity,
    ]

    known = [
        value
        for value in values
        if value in IMPACT_RANK
        and value != "UNKNOWN"
    ]

    if known:
        instability = max(
            known,
            key=lambda value: IMPACT_RANK[value],
        )
    else:
        instability = "UNKNOWN"

    # Fragile recommendation can raise a decision-relevant assumption,
    # but never invent certainty for a completely unknown assumption.
    if (
        robustness is not None
        and robustness.status == "FRAGILE"
        and instability in {
            "LOW",
            "MEDIUM",
        }
    ):
        instability = "HIGH"

    elif (
        robustness is not None
        and robustness.status == "MODERATE"
        and instability == "LOW"
    ):
        instability = "MEDIUM"

    return instability


def _reevaluation_required(
    assumption: DecisionAssumption,
    instability: str,
) -> bool | None:
    if instability in {
        "HIGH",
        "MEDIUM",
    }:
        return True

    if (
        instability == "LOW"
        and assumption.decision_impact == "LOW"
        and assumption.change_sensitivity == "LOW"
    ):
        return False

    # UNKNOWN must not be represented as False.
    return None


def _rationale(
    assumption: DecisionAssumption,
    dimensions: list[str],
    instability: str,
    robustness: RecommendationRobustness | None,
) -> list[str]:
    result: list[str] = []

    if assumption.assumption_type == "PRIORITY":
        result.append(
            "Changing this assumption alters a criterion weight or "
            "relative priority used by the current comparison."
        )

    elif assumption.assumption_type == "CONTEXT":
        result.append(
            "Current architecture, applicability, and integration "
            "judgments were made under this technical context."
        )

    if assumption.decision_impact == "HIGH":
        result.append(
            "The source assumption has high decision impact."
        )

    if assumption.change_sensitivity == "HIGH":
        result.append(
            "The current decision is highly sensitive to changes "
            "in this assumption."
        )

    if (
        robustness is not None
        and robustness.status == "FRAGILE"
    ):
        result.append(
            "The current recommendation is fragile, so assumption "
            "changes require stronger caution."
        )

    if dimensions:
        result.append(
            "Affected dimensions: "
            + ", ".join(dimensions)
            + "."
        )

    if instability == "UNKNOWN":
        result.append(
            "Recommendation instability cannot be determined from "
            "the available decision state."
        )

    return _dedupe(result)


def _impact_rank(
    value: str,
) -> int:
    return IMPACT_RANK.get(
        value,
        0,
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
