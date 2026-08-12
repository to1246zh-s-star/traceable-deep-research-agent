import pytest

from models import (
    Candidate,
    CandidateCriterionScore,
    Constraint,
    DecisionCase,
    DecisionCriterion,
)
from services.decision_comparison import (
    compare_candidates,
    normalize_criterion_weights,
)
from services.decision_evaluator import evaluate_decision_case


def build_decision():
    qdrant = Candidate(name="Qdrant")
    milvus = Candidate(name="Milvus")

    reliability = DecisionCriterion(
        name="Reliability",
        weight=4,
        source="user",
    )

    operations = DecisionCriterion(
        name="Operational simplicity",
        weight=3,
        source="user",
    )

    performance = DecisionCriterion(
        name="Performance",
        weight=3,
        source="user",
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[qdrant, milvus],
        criteria=[
            reliability,
            operations,
            performance,
        ],
    )

    return (
        decision,
        qdrant,
        milvus,
        reliability,
        operations,
        performance,
    )


def test_normalize_criterion_weights():
    (
        decision,
        _,
        _,
        reliability,
        operations,
        performance,
    ) = build_decision()

    weights = normalize_criterion_weights(decision)

    assert weights[reliability.criterion_id] == pytest.approx(0.4)
    assert weights[operations.criterion_id] == pytest.approx(0.3)
    assert weights[performance.criterion_id] == pytest.approx(0.3)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_weighted_candidate_scoring_and_ranking():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        operations,
        performance,
    ) = build_decision()

    evaluation = evaluate_decision_case(decision)

    scores = [
        CandidateCriterionScore(
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            fitness_score=8.5,
        ),
        CandidateCriterionScore(
            candidate_id=qdrant.candidate_id,
            criterion_id=operations.criterion_id,
            fitness_score=9.0,
        ),
        CandidateCriterionScore(
            candidate_id=qdrant.candidate_id,
            criterion_id=performance.criterion_id,
            fitness_score=8.0,
        ),
        CandidateCriterionScore(
            candidate_id=milvus.candidate_id,
            criterion_id=reliability.criterion_id,
            fitness_score=8.7,
        ),
        CandidateCriterionScore(
            candidate_id=milvus.candidate_id,
            criterion_id=operations.criterion_id,
            fitness_score=6.5,
        ),
        CandidateCriterionScore(
            candidate_id=milvus.candidate_id,
            criterion_id=performance.criterion_id,
            fitness_score=9.3,
        ),
    ]

    comparison = compare_candidates(
        decision,
        evaluation,
        scores,
    )

    assert comparison.status == "complete"

    assert comparison.ranked_candidate_ids == [
        qdrant.candidate_id,
        milvus.candidate_id,
    ]

    qdrant_score = comparison.candidate_scores[0]
    milvus_score = comparison.candidate_scores[1]

    assert qdrant_score.rank == 1
    assert milvus_score.rank == 2

    assert qdrant_score.weighted_score == pytest.approx(
        8.5 * 0.4
        + 9.0 * 0.3
        + 8.0 * 0.3
    )

    assert milvus_score.weighted_score == pytest.approx(
        8.7 * 0.4
        + 6.5 * 0.3
        + 9.3 * 0.3
    )


def test_disqualified_candidate_is_excluded_from_ranking():
    qdrant = Candidate(name="Qdrant")
    milvus = Candidate(name="Milvus")

    self_hosted = Constraint(
        text="Must support self-hosting"
    )

    reliability = DecisionCriterion(
        name="Reliability",
        weight=1,
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[qdrant, milvus],
        constraints=[self_hosted],
        criteria=[reliability],
    )

    evaluation = evaluate_decision_case(
        decision,
        constraint_results={
            qdrant.candidate_id: {
                self_hosted.constraint_id: True,
            },
            milvus.candidate_id: {
                self_hosted.constraint_id: False,
            },
        },
    )

    comparison = compare_candidates(
        decision,
        evaluation,
        [
            CandidateCriterionScore(
                candidate_id=qdrant.candidate_id,
                criterion_id=reliability.criterion_id,
                fitness_score=8.0,
            )
        ],
    )

    assert comparison.status == "complete"

    assert comparison.ranked_candidate_ids == [
        qdrant.candidate_id
    ]

    assert comparison.excluded_candidate_ids == [
        milvus.candidate_id
    ]


def test_unresolved_evaluation_blocks_comparison():
    qdrant = Candidate(name="Qdrant")

    self_hosted = Constraint(
        text="Must support self-hosting"
    )

    reliability = DecisionCriterion(
        name="Reliability",
        weight=1,
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[qdrant],
        constraints=[self_hosted],
        criteria=[reliability],
    )

    evaluation = evaluate_decision_case(
        decision,
        constraint_results={},
    )

    comparison = compare_candidates(
        decision,
        evaluation,
        [],
    )

    assert comparison.status == "incomplete"

    assert comparison.ranked_candidate_ids == []

    assert comparison.unresolved_candidate_ids == [
        qdrant.candidate_id
    ]


def test_missing_criterion_score_is_rejected():
    (
        decision,
        qdrant,
        milvus,
        reliability,
        operations,
        performance,
    ) = build_decision()

    evaluation = evaluate_decision_case(decision)

    scores = [
        CandidateCriterionScore(
            candidate_id=qdrant.candidate_id,
            criterion_id=reliability.criterion_id,
            fitness_score=8.0,
        ),
        CandidateCriterionScore(
            candidate_id=qdrant.candidate_id,
            criterion_id=operations.criterion_id,
            fitness_score=8.0,
        ),
        CandidateCriterionScore(
            candidate_id=qdrant.candidate_id,
            criterion_id=performance.criterion_id,
            fitness_score=8.0,
        ),

        CandidateCriterionScore(
            candidate_id=milvus.candidate_id,
            criterion_id=reliability.criterion_id,
            fitness_score=8.0,
        ),
        CandidateCriterionScore(
            candidate_id=milvus.candidate_id,
            criterion_id=operations.criterion_id,
            fitness_score=8.0,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="missing score",
    ):
        compare_candidates(
            decision,
            evaluation,
            scores,
        )


def test_duplicate_candidate_criterion_score_is_rejected():
    candidate = Candidate(name="Qdrant")

    reliability = DecisionCriterion(
        name="Reliability",
        weight=1,
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[candidate],
        criteria=[reliability],
    )

    evaluation = evaluate_decision_case(decision)

    duplicate_scores = [
        CandidateCriterionScore(
            candidate_id=candidate.candidate_id,
            criterion_id=reliability.criterion_id,
            fitness_score=8.0,
        ),
        CandidateCriterionScore(
            candidate_id=candidate.candidate_id,
            criterion_id=reliability.criterion_id,
            fitness_score=9.0,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="duplicate score",
    ):
        compare_candidates(
            decision,
            evaluation,
            duplicate_scores,
        )


@pytest.mark.parametrize(
    "fitness_score",
    [-0.1, 10.1],
)
def test_fitness_score_outside_zero_to_ten_is_rejected(
    fitness_score,
):
    candidate = Candidate(name="Qdrant")

    reliability = DecisionCriterion(
        name="Reliability",
        weight=1,
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[candidate],
        criteria=[reliability],
    )

    evaluation = evaluate_decision_case(decision)

    score = CandidateCriterionScore(
        candidate_id=candidate.candidate_id,
        criterion_id=reliability.criterion_id,
        fitness_score=fitness_score,
    )

    with pytest.raises(
        ValueError,
        match="fitness score must be between",
    ):
        compare_candidates(
            decision,
            evaluation,
            [score],
        )


def test_zero_total_criterion_weight_is_rejected():
    candidate = Candidate(name="Qdrant")

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[candidate],
        criteria=[
            DecisionCriterion(
                name="Reliability",
                weight=0,
            ),
            DecisionCriterion(
                name="Performance",
                weight=0,
            ),
        ],
    )

    evaluation = evaluate_decision_case(decision)

    scores = [
        CandidateCriterionScore(
            candidate_id=candidate.candidate_id,
            criterion_id=criterion.criterion_id,
            fitness_score=8.0,
        )
        for criterion in decision.criteria
    ]

    with pytest.raises(
        ValueError,
        match="criterion weights must have a positive total",
    ):
        compare_candidates(
            decision,
            evaluation,
            scores,
        )


def test_no_criteria_returns_explicit_status():
    candidate = Candidate(name="Qdrant")

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[candidate],
    )

    evaluation = evaluate_decision_case(decision)

    comparison = compare_candidates(
        decision,
        evaluation,
        [],
    )

    assert comparison.status == "no_criteria"
    assert comparison.candidate_scores == []
    assert comparison.ranked_candidate_ids == []
