"""Deterministic re-evaluation triggers for decision intelligence."""

from __future__ import annotations

import hashlib

from models import (
    DecisionAssumption,
    DecisionCase,
    DecisionCounterfactual,
    DecisionReevaluationTrigger,
    DecisionScenario,
)


IMPACT_RANK = {
    "UNKNOWN": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


CONTEXT_INVALIDATION = {
    "existing_stack": [
        "integration_assessment",
        "research_gap_impact",
        "expected_decision_impact",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "deployment_environment": [
        "integration_assessment",
        "research_gap_impact",
        "expected_decision_impact",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "infrastructure": [
        "integration_assessment",
        "research_gap_impact",
        "expected_decision_impact",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "team_capabilities": [
        "integration_assessment",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "scale_requirements": [
        "criterion_scoring",
        "research_gap_analysis",
        "expected_decision_impact",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "performance_requirements": [
        "criterion_scoring",
        "research_gap_analysis",
        "expected_decision_impact",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "reliability_requirements": [
        "criterion_scoring",
        "research_gap_analysis",
        "expected_decision_impact",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "integration_requirements": [
        "integration_assessment",
        "criterion_scoring",
        "research_gap_analysis",
        "expected_decision_impact",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "operational_constraints": [
        "integration_assessment",
        "criterion_scoring",
        "research_gap_analysis",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "security_constraints": [
        "constraint_evaluation",
        "criterion_scoring",
        "research_gap_analysis",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "compliance_constraints": [
        "constraint_evaluation",
        "criterion_scoring",
        "research_gap_analysis",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "migration_constraints": [
        "constraint_evaluation",
        "integration_assessment",
        "research_gap_analysis",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
    "budget_constraints": [
        "constraint_evaluation",
        "criterion_scoring",
        "research_gap_analysis",
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ],
}


PRIORITY_INVALIDATION = [
    "decision_comparison",
    "decision_sensitivity",
    "recommendation_robustness",
    "research_gap_impact",
    "expected_decision_impact",
    "assumption_analysis",
    "counterfactual_analysis",
    "scenario_analysis",
]


def derive_reevaluation_triggers(
    decision: DecisionCase,
    assumptions: list[DecisionAssumption],
    counterfactuals: list[DecisionCounterfactual],
    scenarios: list[DecisionScenario],
) -> list[DecisionReevaluationTrigger]:
    """
    Build deterministic triggers from explicit assumption dependencies.

    No new scores, rankings, or hypothetical outcomes are generated.
    """

    assumption_by_id = {
        item.assumption_id: item
        for item in assumptions
        if item.decision_id == decision.decision_id
    }

    counterfactual_by_assumption: dict[
        str,
        list[DecisionCounterfactual],
    ] = {}

    for item in counterfactuals:
        if item.decision_id != decision.decision_id:
            continue

        counterfactual_by_assumption.setdefault(
            item.assumption_id,
            [],
        ).append(item)

    scenario_ids_by_counterfactual: dict[
        str,
        list[str],
    ] = {}

    for scenario in scenarios:
        if scenario.decision_id != decision.decision_id:
            continue

        for counterfactual_id in scenario.counterfactual_ids:
            scenario_ids_by_counterfactual.setdefault(
                counterfactual_id,
                [],
            ).append(
                scenario.scenario_id
            )

    result: list[DecisionReevaluationTrigger] = []

    for assumption_id, assumption in assumption_by_id.items():
        related_counterfactuals = (
            counterfactual_by_assumption.get(
                assumption_id,
                [],
            )
        )

        result.append(
            _build_trigger(
                decision,
                assumption,
                related_counterfactuals,
                scenario_ids_by_counterfactual,
            )
        )

    return sorted(
        result,
        key=lambda item: (
            -_impact_rank(
                item.trigger_impact
            ),
            item.trigger_type,
            item.source_field or "",
            item.source_value or "",
            item.trigger_id,
        ),
    )


def _build_trigger(
    decision: DecisionCase,
    assumption: DecisionAssumption,
    counterfactuals: list[DecisionCounterfactual],
    scenario_ids_by_counterfactual: dict[str, list[str]],
) -> DecisionReevaluationTrigger:
    impact = _trigger_impact(
        assumption,
        counterfactuals,
    )

    required = _reevaluation_required(
        assumption,
        counterfactuals,
        impact,
    )

    invalidated_modules = (
        _invalidated_modules(
            assumption
        )
    )

    scenario_ids = _dedupe(
        [
            scenario_id
            for item in counterfactuals
            for scenario_id
            in scenario_ids_by_counterfactual.get(
                item.counterfactual_id,
                [],
            )
        ]
    )

    candidate_ids = _valid_candidates(
        decision,
        assumption.affected_candidate_ids,
    )

    criterion_ids = _valid_criteria(
        decision,
        assumption.affected_criterion_ids,
    )

    return DecisionReevaluationTrigger(
        trigger_id=_trigger_id(
            decision.decision_id,
            assumption,
        ),
        decision_id=decision.decision_id,
        trigger_type=_trigger_type(
            assumption
        ),
        source_type=assumption.source_type,
        source_field=assumption.source_field,
        source_value=assumption.source_value,
        affected_candidate_ids=candidate_ids,
        affected_criterion_ids=criterion_ids,
        affected_scenario_ids=scenario_ids,
        invalidated_modules=invalidated_modules,
        trigger_impact=impact,
        reevaluation_required=required,
        rationale=_rationale(
            assumption,
            counterfactuals,
            invalidated_modules,
            impact,
        ),
    )


def _trigger_type(
    assumption: DecisionAssumption,
) -> str:
    if assumption.assumption_type == "PRIORITY":
        return "CRITERION_PRIORITY_CHANGE"

    if assumption.assumption_type == "CONTEXT":
        return "TECHNICAL_CONTEXT_CHANGE"

    return "ASSUMPTION_CHANGE"


def _invalidated_modules(
    assumption: DecisionAssumption,
) -> list[str]:
    if assumption.assumption_type == "PRIORITY":
        return list(
            PRIORITY_INVALIDATION
        )

    if assumption.assumption_type == "CONTEXT":
        return list(
            CONTEXT_INVALIDATION.get(
                assumption.source_field or "",
                [
                    "assumption_analysis",
                    "counterfactual_analysis",
                    "scenario_analysis",
                ],
            )
        )

    return [
        "assumption_analysis",
        "counterfactual_analysis",
        "scenario_analysis",
    ]


def _trigger_impact(
    assumption: DecisionAssumption,
    counterfactuals: list[DecisionCounterfactual],
) -> str:
    values = [
        assumption.decision_impact,
        assumption.change_sensitivity,
        *[
            item.recommendation_instability
            for item in counterfactuals
        ],
    ]

    known = [
        value
        for value in values
        if (
            value in IMPACT_RANK
            and value != "UNKNOWN"
        )
    ]

    if not known:
        return "UNKNOWN"

    return max(
        known,
        key=lambda value: IMPACT_RANK[value],
    )


def _reevaluation_required(
    assumption: DecisionAssumption,
    counterfactuals: list[DecisionCounterfactual],
    impact: str,
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

    if impact in {
        "HIGH",
        "MEDIUM",
    }:
        return True

    if any(
        value is None
        for value in values
    ):
        return None

    if (
        impact == "LOW"
        and assumption.decision_impact == "LOW"
        and assumption.change_sensitivity == "LOW"
    ):
        return False

    return None


def _rationale(
    assumption: DecisionAssumption,
    counterfactuals: list[DecisionCounterfactual],
    invalidated_modules: list[str],
    impact: str,
) -> list[str]:
    result: list[str] = []

    if assumption.assumption_type == "CONTEXT":
        result.append(
            "The current decision intelligence depends on this "
            "explicit technical context."
        )

    elif assumption.assumption_type == "PRIORITY":
        result.append(
            "The current ranking depends on this criterion priority."
        )

    if counterfactuals:
        result.append(
            f"{len(counterfactuals)} counterfactual dependency "
            f"path(s) are linked to this assumption."
        )

    if invalidated_modules:
        result.append(
            "Recompute affected modules: "
            + ", ".join(
                invalidated_modules
            )
            + "."
        )

    if impact == "HIGH":
        result.append(
            "This trigger has high decision impact."
        )

    elif impact == "UNKNOWN":
        result.append(
            "Trigger impact cannot be fully determined from the "
            "available decision state."
        )

    return _dedupe(result)


def _trigger_id(
    decision_id: str,
    assumption: DecisionAssumption,
) -> str:
    payload = "|".join(
        [
            decision_id,
            assumption.assumption_id,
            assumption.source_type,
            assumption.source_field or "",
            assumption.source_value or "",
        ]
    )

    digest = hashlib.sha1(
        payload.encode("utf-8")
    ).hexdigest()[:12]

    return f"trg_{digest}"


def _valid_candidates(
    decision: DecisionCase,
    values: list[str],
) -> list[str]:
    valid = {
        candidate.candidate_id
        for candidate in decision.candidates
    }

    return _dedupe(
        [
            value
            for value in values
            if value in valid
        ]
    )


def _valid_criteria(
    decision: DecisionCase,
    values: list[str],
) -> list[str]:
    valid = {
        criterion.criterion_id
        for criterion in decision.criteria
    }

    return _dedupe(
        [
            value
            for value in values
            if value in valid
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
