"""Deterministic scenario analysis for technical decisions."""

from __future__ import annotations

import hashlib

from models import (
    DecisionCase,
    DecisionCounterfactual,
    DecisionScenario,
)


IMPACT_RANK = {
    "UNKNOWN": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


SCENARIO_FIELDS = {
    "ARCHITECTURE": {
        "existing_stack",
        "deployment_environment",
        "infrastructure",
        "integration_requirements",
        "migration_constraints",
    },
    "DELIVERY": {
        "team_capabilities",
        "operational_constraints",
    },
    "SCALE_PERFORMANCE": {
        "scale_requirements",
        "performance_requirements",
        "reliability_requirements",
    },
    "GOVERNANCE": {
        "security_constraints",
        "compliance_constraints",
    },
    "ECONOMICS": {
        "budget_constraints",
    },
}


SCENARIO_TITLES = {
    "ARCHITECTURE": "Architecture context changes",
    "DELIVERY": "Delivery and operating model changes",
    "SCALE_PERFORMANCE": "Scale and performance requirements change",
    "GOVERNANCE": "Governance requirements change",
    "ECONOMICS": "Economic constraints change",
    "PRIORITY": "Decision priorities change",
    "OTHER": "Other decision assumptions change",
}


def analyze_decision_scenarios(
    decision: DecisionCase,
    counterfactuals: list[DecisionCounterfactual],
) -> list[DecisionScenario]:
    """
    Combine existing counterfactuals into bounded technical scenarios.

    No hypothetical candidate scores or predicted winners are generated.
    """

    relevant = [
        item
        for item in counterfactuals
        if item.decision_id == decision.decision_id
    ]

    grouped: dict[
        str,
        list[DecisionCounterfactual],
    ] = {}

    for counterfactual in relevant:
        scenario_type = _scenario_type(
            counterfactual
        )

        grouped.setdefault(
            scenario_type,
            [],
        ).append(counterfactual)

    scenarios = [
        _build_scenario(
            decision,
            scenario_type,
            items,
        )
        for scenario_type, items
        in grouped.items()
    ]

    return sorted(
        scenarios,
        key=lambda item: (
            -_impact_rank(
                item.scenario_instability
            ),
            item.scenario_type,
            item.scenario_id,
        ),
    )


def _build_scenario(
    decision: DecisionCase,
    scenario_type: str,
    counterfactuals: list[DecisionCounterfactual],
) -> DecisionScenario:
    ordered = sorted(
        counterfactuals,
        key=lambda item: (
            item.assumption_id,
            item.counterfactual_id,
        ),
    )

    instability = _aggregate_instability(
        ordered
    )

    reevaluation_required = (
        _aggregate_reevaluation(
            ordered,
            instability,
        )
    )

    affected_candidate_ids = _valid_candidates(
        decision,
        [
            candidate_id
            for item in ordered
            for candidate_id
            in item.affected_candidate_ids
        ],
    )

    affected_criterion_ids = _valid_criteria(
        decision,
        [
            criterion_id
            for item in ordered
            for criterion_id
            in item.affected_criterion_ids
        ],
    )

    affected_dimensions = _dedupe(
        [
            dimension
            for item in ordered
            for dimension
            in item.affected_dimensions
        ]
    )

    counterfactual_ids = [
        item.counterfactual_id
        for item in ordered
    ]

    assumption_ids = _dedupe(
        [
            item.assumption_id
            for item in ordered
        ]
    )

    return DecisionScenario(
        scenario_id=_scenario_id(
            decision.decision_id,
            scenario_type,
            counterfactual_ids,
        ),
        decision_id=decision.decision_id,
        scenario_type=scenario_type,
        title=SCENARIO_TITLES[
            scenario_type
        ],
        counterfactual_ids=counterfactual_ids,
        assumption_ids=assumption_ids,
        affected_candidate_ids=affected_candidate_ids,
        affected_criterion_ids=affected_criterion_ids,
        affected_dimensions=affected_dimensions,
        scenario_instability=instability,
        reevaluation_required=reevaluation_required,
        rationale=_scenario_rationale(
            scenario_type,
            ordered,
            instability,
            affected_dimensions,
        ),
    )


def _scenario_type(
    counterfactual: DecisionCounterfactual,
) -> str:
    if counterfactual.assumption_type == "PRIORITY":
        return "PRIORITY"

    field = counterfactual.source_field

    for scenario_type, fields in SCENARIO_FIELDS.items():
        if field in fields:
            return scenario_type

    return "OTHER"


def _aggregate_instability(
    counterfactuals: list[DecisionCounterfactual],
) -> str:
    known = [
        item.recommendation_instability
        for item in counterfactuals
        if (
            item.recommendation_instability
            in IMPACT_RANK
            and item.recommendation_instability
            != "UNKNOWN"
        )
    ]

    if not known:
        return "UNKNOWN"

    # Deliberately use max observed instability.
    # Do not invent an extra escalation merely because
    # several counterfactuals are grouped together.
    return max(
        known,
        key=lambda value: IMPACT_RANK[value],
    )


def _aggregate_reevaluation(
    counterfactuals: list[DecisionCounterfactual],
    instability: str,
) -> bool | None:
    values = [
        item.reevaluation_required
        for item in counterfactuals
    ]

    if any(
        value is True
        for value in values
    ):
        return True

    if any(
        value is None
        for value in values
    ):
        return None

    if (
        values
        and all(
            value is False
            for value in values
        )
        and instability == "LOW"
    ):
        return False

    return None


def _scenario_rationale(
    scenario_type: str,
    counterfactuals: list[DecisionCounterfactual],
    instability: str,
    affected_dimensions: list[str],
) -> list[str]:
    result = [
        (
            f"This scenario groups "
            f"{len(counterfactuals)} explicit counterfactual(s) "
            f"in the {scenario_type} decision domain."
        )
    ]

    if affected_dimensions:
        result.append(
            "Affected dimensions: "
            + ", ".join(
                affected_dimensions
            )
            + "."
        )

    if instability == "HIGH":
        result.append(
            "At least one underlying counterfactual has high "
            "recommendation instability."
        )

    elif instability == "MEDIUM":
        result.append(
            "At least one underlying counterfactual has moderate "
            "recommendation instability."
        )

    elif instability == "UNKNOWN":
        result.append(
            "Scenario instability cannot be fully determined from "
            "the available counterfactual state."
        )

    return result


def _scenario_id(
    decision_id: str,
    scenario_type: str,
    counterfactual_ids: list[str],
) -> str:
    payload = "|".join(
        [
            decision_id,
            scenario_type,
            *sorted(counterfactual_ids),
        ]
    )

    digest = hashlib.sha1(
        payload.encode("utf-8")
    ).hexdigest()[:12]

    return f"scn_{digest}"


def _valid_candidates(
    decision: DecisionCase,
    candidate_ids: list[str],
) -> list[str]:
    valid = {
        candidate.candidate_id
        for candidate in decision.candidates
    }

    return _dedupe(
        [
            candidate_id
            for candidate_id in candidate_ids
            if candidate_id in valid
        ]
    )


def _valid_criteria(
    decision: DecisionCase,
    criterion_ids: list[str],
) -> list[str]:
    valid = {
        criterion.criterion_id
        for criterion in decision.criteria
    }

    return _dedupe(
        [
            criterion_id
            for criterion_id in criterion_ids
            if criterion_id in valid
        ]
    )


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
