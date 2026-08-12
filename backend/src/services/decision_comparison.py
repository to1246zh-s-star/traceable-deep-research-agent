"""Deterministic candidate comparison for V3 Phase 8."""

from models import (
    CandidateCriterionScore,
    CandidateWeightedScore,
    DecisionCase,
    DecisionComparison,
    DecisionEvaluation,
)


MIN_FITNESS_SCORE = 0.0
MAX_FITNESS_SCORE = 10.0


def validate_criterion_scores(
    decision: DecisionCase,
    evaluation: DecisionEvaluation,
    criterion_scores: list[CandidateCriterionScore],
) -> None:
    """Validate score coverage and structural consistency."""

    candidate_ids = {
        candidate.candidate_id
        for candidate in decision.candidates
    }

    criterion_ids = {
        criterion.criterion_id
        for criterion in decision.criteria
    }

    eligible_ids = set(evaluation.eligible_candidate_ids)

    seen_pairs: set[tuple[str, str]] = set()
    errors: list[str] = []

    for score in criterion_scores:
        if score.candidate_id not in candidate_ids:
            errors.append(
                f"unknown candidate_id {score.candidate_id!r}"
            )

        if score.criterion_id not in criterion_ids:
            errors.append(
                f"unknown criterion_id {score.criterion_id!r}"
            )

        if score.candidate_id not in eligible_ids:
            errors.append(
                f"candidate {score.candidate_id!r} is not eligible for scoring"
            )

        if not (
            MIN_FITNESS_SCORE
            <= score.fitness_score
            <= MAX_FITNESS_SCORE
        ):
            errors.append(
                f"fitness score must be between "
                f"{MIN_FITNESS_SCORE} and {MAX_FITNESS_SCORE}"
            )

        pair = (
            score.candidate_id,
            score.criterion_id,
        )

        if pair in seen_pairs:
            errors.append(
                f"duplicate score for candidate {score.candidate_id!r} "
                f"and criterion {score.criterion_id!r}"
            )

        seen_pairs.add(pair)

    for candidate_id in eligible_ids:
        for criterion_id in criterion_ids:
            if (candidate_id, criterion_id) not in seen_pairs:
                errors.append(
                    f"missing score for candidate {candidate_id!r} "
                    f"and criterion {criterion_id!r}"
                )

    if errors:
        raise ValueError("; ".join(errors))


def normalize_criterion_weights(
    decision: DecisionCase,
) -> dict[str, float]:
    """
    Normalize criterion weights to sum to 1.

    Raw user weights do not need to already sum to 1.
    """

    if not decision.criteria:
        return {}

    total_weight = sum(
        criterion.weight
        for criterion in decision.criteria
    )

    if total_weight <= 0:
        raise ValueError(
            "criterion weights must have a positive total"
        )

    return {
        criterion.criterion_id: criterion.weight / total_weight
        for criterion in decision.criteria
    }


def compare_candidates(
    decision: DecisionCase,
    evaluation: DecisionEvaluation,
    criterion_scores: list[CandidateCriterionScore],
) -> DecisionComparison:
    """
    Compare eligible candidates with deterministic weighted scoring.

    Phase 7 owns hard-constraint eligibility.
    Phase 8 only scores candidates that Phase 7 marked eligible.
    """

    if evaluation.decision_id != decision.decision_id:
        raise ValueError(
            "evaluation does not belong to the supplied decision"
        )

    if evaluation.status != "complete":
        return DecisionComparison(
            decision_id=decision.decision_id,
            status="incomplete",
            excluded_candidate_ids=list(
                evaluation.disqualified_candidate_ids
            ),
            unresolved_candidate_ids=list(
                evaluation.unresolved_candidate_ids
            ),
        )

    if not decision.criteria:
        return DecisionComparison(
            decision_id=decision.decision_id,
            status="no_criteria",
            excluded_candidate_ids=list(
                evaluation.disqualified_candidate_ids
            ),
        )

    validate_criterion_scores(
        decision,
        evaluation,
        criterion_scores,
    )

    normalized_weights = normalize_criterion_weights(decision)

    scores_by_candidate: dict[
        str,
        list[CandidateCriterionScore],
    ] = {
        candidate_id: []
        for candidate_id in evaluation.eligible_candidate_ids
    }

    for score in criterion_scores:
        scores_by_candidate[score.candidate_id].append(score)

    candidate_scores: list[CandidateWeightedScore] = []

    for candidate_id in evaluation.eligible_candidate_ids:
        scores = scores_by_candidate[candidate_id]

        weighted_score = sum(
            score.fitness_score
            * normalized_weights[score.criterion_id]
            for score in scores
        )

        candidate_scores.append(
            CandidateWeightedScore(
                candidate_id=candidate_id,
                weighted_score=weighted_score,
                criterion_scores=scores,
            )
        )

    candidate_scores.sort(
        key=lambda item: (
            -item.weighted_score,
            item.candidate_id,
        )
    )

    for index, candidate_score in enumerate(
        candidate_scores,
        start=1,
    ):
        candidate_score.rank = index

    ranked_candidate_ids = [
        candidate_score.candidate_id
        for candidate_score in candidate_scores
    ]

    return DecisionComparison(
        decision_id=decision.decision_id,
        status="complete",
        candidate_scores=candidate_scores,
        ranked_candidate_ids=ranked_candidate_ids,
        excluded_candidate_ids=list(
            evaluation.disqualified_candidate_ids
        ),
    )
