"""Deterministic recommendation sensitivity analysis."""

from __future__ import annotations

from models import (
    CandidateCriterionScore,
    DecisionCase,
    DecisionComparison,
    SensitivityResult,
)


DEFAULT_WEIGHT_STEP = 0.01
_EPSILON = 1e-9


def analyze_decision_sensitivity(
    decision: DecisionCase,
    comparison: DecisionComparison,
    criterion_scores: list[CandidateCriterionScore],
    *,
    weight_step: float = DEFAULT_WEIGHT_STEP,
) -> list[SensitivityResult]:
    """
    Analyze how criterion-weight changes affect the baseline recommendation.

    Only complete deterministic comparisons are analyzed. Missing or
    unresolved decision state produces no sensitivity result rather than
    inventing a neutral threshold.
    """

    if comparison.status != "complete":
        return []

    ranked_ids = list(comparison.ranked_candidate_ids)

    if len(ranked_ids) < 2 or not decision.criteria:
        return []

    if weight_step <= 0:
        raise ValueError("weight_step must be positive")

    baseline_winner_id = ranked_ids[0]

    candidate_score_map = {
        item.candidate_id: item.weighted_score
        for item in comparison.candidate_scores
    }

    if any(
        candidate_id not in candidate_score_map
        for candidate_id in ranked_ids
    ):
        return []

    baseline_runner_up_id = ranked_ids[1]

    baseline_margin = (
        candidate_score_map[baseline_winner_id]
        - candidate_score_map[baseline_runner_up_id]
    )

    # A tied baseline does not represent a unique recommendation.
    if baseline_margin <= _EPSILON:
        return []

    fitness_by_pair = {
        (score.candidate_id, score.criterion_id): score.fitness_score
        for score in criterion_scores
    }

    criterion_ids = [
        criterion.criterion_id
        for criterion in decision.criteria
    ]

    for candidate_id in ranked_ids:
        for criterion_id in criterion_ids:
            if (candidate_id, criterion_id) not in fitness_by_pair:
                return []

    weights = {
        criterion.criterion_id: criterion.weight
        for criterion in decision.criteria
    }

    if any(weight < 0 for weight in weights.values()):
        raise ValueError("criterion weights must be non-negative")

    total_weight = sum(weights.values())

    if total_weight <= _EPSILON:
        return []

    absolute_step = weight_step * total_weight

    results: list[SensitivityResult] = []

    for criterion in decision.criteria:
        baseline_weight = weights[criterion.criterion_id]

        decrease_flip = _find_flip(
            criterion_id=criterion.criterion_id,
            direction="decrease",
            baseline_weight=baseline_weight,
            total_weight=total_weight,
            absolute_step=absolute_step,
            weights=weights,
            ranked_candidate_ids=ranked_ids,
            baseline_winner_id=baseline_winner_id,
            fitness_by_pair=fitness_by_pair,
        )

        increase_flip = _find_flip(
            criterion_id=criterion.criterion_id,
            direction="increase",
            baseline_weight=baseline_weight,
            total_weight=total_weight,
            absolute_step=absolute_step,
            weights=weights,
            ranked_candidate_ids=ranked_ids,
            baseline_winner_id=baseline_winner_id,
            fitness_by_pair=fitness_by_pair,
        )

        flip = _nearest_flip(
            decrease_flip,
            increase_flip,
            baseline_weight=baseline_weight,
        )

        if flip is None:
            results.append(
                SensitivityResult(
                    decision_id=decision.decision_id,
                    criterion_id=criterion.criterion_id,
                    baseline_weight=baseline_weight,
                    baseline_winner_id=baseline_winner_id,
                    score_margin_before=baseline_margin,
                )
            )
            continue

        threshold, competing_id, margin_after, direction = flip

        results.append(
            SensitivityResult(
                decision_id=decision.decision_id,
                criterion_id=criterion.criterion_id,
                baseline_weight=baseline_weight,
                baseline_winner_id=baseline_winner_id,
                score_margin_before=baseline_margin,
                recommendation_changes=True,
                switch_threshold=threshold,
                weight_delta=threshold - baseline_weight,
                direction_of_change=direction,
                competing_candidate_id=competing_id,
                # Convention:
                # baseline winner minus new winner, therefore negative
                # after a genuine recommendation flip.
                score_margin_after=margin_after,
            )
        )

    return results


def _find_flip(
    *,
    criterion_id: str,
    direction: str,
    baseline_weight: float,
    total_weight: float,
    absolute_step: float,
    weights: dict[str, float],
    ranked_candidate_ids: list[str],
    baseline_winner_id: str,
    fitness_by_pair: dict[tuple[str, str], float],
) -> tuple[float, str, float, str] | None:
    if direction == "decrease":
        targets = _descending_targets(
            baseline_weight,
            absolute_step,
        )
    elif direction == "increase":
        targets = _ascending_targets(
            baseline_weight,
            total_weight,
            absolute_step,
        )
    else:
        raise ValueError(f"unknown sensitivity direction: {direction}")

    for target_weight in targets:
        perturbed_weights = _renormalize_weights(
            weights,
            criterion_id=criterion_id,
            target_weight=target_weight,
            total_weight=total_weight,
        )

        candidate_scores = {
            candidate_id: sum(
                fitness_by_pair[(candidate_id, current_criterion_id)]
                * current_weight
                for current_criterion_id, current_weight
                in perturbed_weights.items()
            )
            for candidate_id in ranked_candidate_ids
        }

        baseline_score = candidate_scores[baseline_winner_id]

        challengers = [
            (
                candidate_scores[candidate_id],
                candidate_id,
            )
            for candidate_id in ranked_candidate_ids
            if candidate_id != baseline_winner_id
        ]

        # Deterministic tie-break by candidate id.
        challenger_score, challenger_id = max(
            challengers,
            key=lambda item: (item[0], item[1]),
        )

        # Tie is instability, but not yet a recommendation flip.
        if challenger_score > baseline_score + _EPSILON:
            return (
                target_weight,
                challenger_id,
                baseline_score - challenger_score,
                direction,
            )

    return None


def _renormalize_weights(
    weights: dict[str, float],
    *,
    criterion_id: str,
    target_weight: float,
    total_weight: float,
) -> dict[str, float]:
    baseline_weight = weights[criterion_id]

    other_total = total_weight - baseline_weight
    remaining_weight = total_weight - target_weight

    result: dict[str, float] = {
        criterion_id: target_weight,
    }

    if other_total <= _EPSILON:
        for other_id in weights:
            if other_id != criterion_id:
                result[other_id] = 0.0
        return result

    for other_id, other_weight in weights.items():
        if other_id == criterion_id:
            continue

        result[other_id] = (
            remaining_weight
            * other_weight
            / other_total
        )

    return result


def _descending_targets(
    baseline_weight: float,
    step: float,
) -> list[float]:
    targets: list[float] = []
    current = baseline_weight - step

    while current > _EPSILON:
        targets.append(current)
        current -= step

    if baseline_weight > _EPSILON:
        targets.append(0.0)

    return targets


def _ascending_targets(
    baseline_weight: float,
    total_weight: float,
    step: float,
) -> list[float]:
    targets: list[float] = []
    current = baseline_weight + step

    while current < total_weight - _EPSILON:
        targets.append(current)
        current += step

    if baseline_weight < total_weight - _EPSILON:
        targets.append(total_weight)

    return targets


def _nearest_flip(
    decrease_flip: tuple[float, str, float, str] | None,
    increase_flip: tuple[float, str, float, str] | None,
    *,
    baseline_weight: float,
) -> tuple[float, str, float, str] | None:
    if decrease_flip is None:
        return increase_flip

    if increase_flip is None:
        return decrease_flip

    decrease_distance = abs(
        decrease_flip[0] - baseline_weight
    )
    increase_distance = abs(
        increase_flip[0] - baseline_weight
    )

    # Deterministic tie-break: decrease first.
    if decrease_distance <= increase_distance:
        return decrease_flip

    return increase_flip
