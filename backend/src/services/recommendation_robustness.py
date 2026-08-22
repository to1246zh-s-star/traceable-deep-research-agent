"""Deterministic robustness analysis for technical recommendations."""

from __future__ import annotations

from collections import defaultdict

from models import (
    DecisionCase,
    DecisionComparison,
    DecisionEvaluation,
    DecisionReadiness,
    EvidenceAssessment,
    EvidenceSignal,
    IntegrationAssessment,
    RecommendationRobustness,
    SensitivityResult,
)


WEAK_EVIDENCE_THRESHOLD = 0.50
LOW_READINESS_THRESHOLD = 0.50
MODERATE_READINESS_THRESHOLD = 0.75
LOW_AGREEMENT_THRESHOLD = 0.70
LOW_MARGIN_THRESHOLD = 0.15

# A winner that flips after changing one criterion by <=10% of the
# original total criterion weight is considered locally fragile.
NEAR_FLIP_RELATIVE_DELTA = 0.10

ARCHITECTURE_FIELDS = (
    "integration_complexity",
    "migration_complexity",
    "operational_change",
    "infrastructure_change",
)


def analyze_recommendation_robustness(
    decision: DecisionCase,
    comparison: DecisionComparison,
    evaluation: DecisionEvaluation,
    sensitivity: list[SensitivityResult],
    readiness: DecisionReadiness | None,
    evidence_assessments: list[EvidenceAssessment],
    evidence_signals: list[EvidenceSignal],
    integration_assessments: list[IntegrationAssessment],
) -> RecommendationRobustness:
    """
    Determine how stable the current recommendation is.

    The analyzer never changes candidate ranking. It only explains whether
    the deterministic winner is robust to known uncertainty and weight
    perturbations.
    """

    result = RecommendationRobustness(
        decision_id=decision.decision_id,
    )

    if comparison.decision_id != decision.decision_id:
        result.reasons.append(
            "Decision comparison does not belong to this decision."
        )
        return result

    if evaluation.decision_id != decision.decision_id:
        result.reasons.append(
            "Decision evaluation does not belong to this decision."
        )
        return result

    if (
        comparison.status != "complete"
        or len(comparison.ranked_candidate_ids) < 2
        or len(comparison.candidate_scores) < 2
    ):
        result.unresolved_candidate_ids = list(
            comparison.unresolved_candidate_ids
            or evaluation.unresolved_candidate_ids
        )
        result.reasons.append(
            "Recommendation robustness is unknown because the "
            "candidate comparison is incomplete."
        )
        return result

    winner_id = comparison.ranked_candidate_ids[0]
    runner_up_id = comparison.ranked_candidate_ids[1]

    result.baseline_winner_id = winner_id

    score_by_candidate = {
        item.candidate_id: item.weighted_score
        for item in comparison.candidate_scores
    }

    winner_score = score_by_candidate.get(winner_id)
    runner_up_score = score_by_candidate.get(runner_up_id)

    if winner_score is None or runner_up_score is None:
        result.reasons.append(
            "Recommendation robustness is unknown because ranked "
            "candidate scores are missing."
        )
        return result

    result.score_margin = (
        winner_score - runner_up_score
    )

    result.unresolved_candidate_ids = list(
        evaluation.unresolved_candidate_ids
    )

    relevant_sensitivity = [
        item
        for item in sensitivity
        if (
            item.decision_id == decision.decision_id
            and item.baseline_winner_id == winner_id
        )
    ]

    result.tested_criteria_count = len(
        relevant_sensitivity
    )

    changing_results = [
        item
        for item in relevant_sensitivity
        if item.recommendation_changes
    ]

    result.flip_count = len(changing_results)

    result.unstable_criterion_ids = [
        item.criterion_id
        for item in changing_results
    ]

    deltas = [
        abs(item.weight_delta)
        for item in changing_results
        if item.weight_delta is not None
    ]

    if deltas:
        result.minimum_flip_delta = min(deltas)

    total_weight = sum(
        criterion.weight
        for criterion in decision.criteria
    )

    relative_deltas = [
        abs(item.weight_delta) / total_weight
        for item in changing_results
        if (
            item.weight_delta is not None
            and total_weight > 0
        )
    ]

    if relative_deltas:
        result.minimum_relative_flip_delta = min(
            relative_deltas
        )

    result.weak_evidence_candidate_ids = (
        _weak_evidence_candidates(
            evidence_assessments,
            evidence_signals,
        )
    )

    result.architecture_unknown_candidate_ids = (
        _architecture_unknown_candidates(
            decision,
            integration_assessments,
        )
    )

    if readiness is not None:
        result.readiness_status = readiness.status

    # ---------------------------------------------------------------
    # Hard FRAGILE conditions
    # ---------------------------------------------------------------

    fragile_reasons: list[str] = []

    if result.unresolved_candidate_ids:
        fragile_reasons.append(
            "One or more candidate hard constraints remain unresolved."
        )

    if (
        result.minimum_relative_flip_delta is not None
        and result.minimum_relative_flip_delta
        <= NEAR_FLIP_RELATIVE_DELTA
    ):
        fragile_reasons.append(
            "The recommendation changes under a small criterion-weight "
            "perturbation."
        )

    if (
        readiness is not None
        and readiness.overall_score
        < LOW_READINESS_THRESHOLD
    ):
        fragile_reasons.append(
            "Overall decision readiness is low."
        )

    if fragile_reasons:
        result.status = "FRAGILE"
        result.reasons.extend(fragile_reasons)
        result.reasons.extend(
            _secondary_reasons(
                winner_id,
                result,
                readiness,
            )
        )
        return result

    # ---------------------------------------------------------------
    # MODERATE conditions
    # ---------------------------------------------------------------

    moderate_reasons: list[str] = []

    if result.flip_count > 0:
        moderate_reasons.append(
            "The recommendation changes under at least one tested "
            "criterion-weight perturbation."
        )

    if winner_id in result.weak_evidence_candidate_ids:
        moderate_reasons.append(
            "The current winner is supported mainly by weak assessed evidence."
        )

    if (
        winner_id
        in result.architecture_unknown_candidate_ids
    ):
        moderate_reasons.append(
            "Architecture fit for the current winner is not fully resolved."
        )

    if readiness is not None:
        if (
            readiness.overall_score
            < MODERATE_READINESS_THRESHOLD
        ):
            moderate_reasons.append(
                "Decision readiness is below the robust threshold."
            )

        if (
            readiness.agreement_score
            < LOW_AGREEMENT_THRESHOLD
        ):
            moderate_reasons.append(
                "Available evidence has limited agreement."
            )

        if (
            readiness.decision_margin
            < LOW_MARGIN_THRESHOLD
        ):
            moderate_reasons.append(
                "The normalized decision margin is narrow."
            )

    if moderate_reasons:
        result.status = "MODERATE"
        result.reasons.extend(
            _dedupe(moderate_reasons)
        )
        return result

    # ---------------------------------------------------------------
    # ROBUST
    # ---------------------------------------------------------------

    result.status = "ROBUST"

    if relevant_sensitivity:
        result.reasons.append(
            "No tested criterion-weight perturbation changed the winner."
        )
    else:
        result.reasons.append(
            "The comparison is complete and no sensitivity instability "
            "was detected."
        )

    result.reasons.append(
        "No unresolved hard constraints block the current recommendation."
    )

    return result


def _weak_evidence_candidates(
    assessments: list[EvidenceAssessment],
    signals: list[EvidenceSignal],
) -> list[str]:
    """
    Mark a candidate weak only when it has assessed evidence and the mean
    score across its unique evidence items is below the threshold.

    Missing evidence is not treated as weak evidence here; incompleteness is
    handled elsewhere in the decision pipeline.
    """

    score_by_evidence = {
        assessment.evidence_id:
            assessment.overall_score
        for assessment in assessments
    }

    evidence_ids_by_candidate: dict[
        str,
        set[str],
    ] = defaultdict(set)

    for signal in signals:
        if signal.evidence_id in score_by_evidence:
            evidence_ids_by_candidate[
                signal.candidate_id
            ].add(signal.evidence_id)

    weak: list[str] = []

    for (
        candidate_id,
        evidence_ids,
    ) in evidence_ids_by_candidate.items():
        scores = [
            score_by_evidence[evidence_id]
            for evidence_id in evidence_ids
        ]

        if (
            scores
            and sum(scores) / len(scores)
            < WEAK_EVIDENCE_THRESHOLD
        ):
            weak.append(candidate_id)

    return sorted(weak)


def _architecture_unknown_candidates(
    decision: DecisionCase,
    assessments: list[IntegrationAssessment],
) -> list[str]:
    """
    Missing assessment or any unresolved core architecture dimension makes
    candidate architecture fit incomplete.
    """

    by_candidate = {
        assessment.candidate_id:
            assessment
        for assessment in assessments
        if assessment.decision_id
        == decision.decision_id
    }

    unknown: list[str] = []

    for candidate in decision.candidates:
        assessment = by_candidate.get(
            candidate.candidate_id
        )

        if assessment is None:
            unknown.append(
                candidate.candidate_id
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
            unknown.append(
                candidate.candidate_id
            )

    return unknown


def _secondary_reasons(
    winner_id: str,
    result: RecommendationRobustness,
    readiness: DecisionReadiness | None,
) -> list[str]:
    reasons: list[str] = []

    if winner_id in result.weak_evidence_candidate_ids:
        reasons.append(
            "The current winner is supported mainly by weak assessed evidence."
        )

    if (
        winner_id
        in result.architecture_unknown_candidate_ids
    ):
        reasons.append(
            "Architecture fit for the current winner is not fully resolved."
        )

    if (
        readiness is not None
        and readiness.agreement_score
        < LOW_AGREEMENT_THRESHOLD
    ):
        reasons.append(
            "Available evidence has limited agreement."
        )

    if (
        readiness is not None
        and readiness.decision_margin
        < LOW_MARGIN_THRESHOLD
    ):
        reasons.append(
            "The normalized decision margin is narrow."
        )

    return _dedupe(reasons)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result
