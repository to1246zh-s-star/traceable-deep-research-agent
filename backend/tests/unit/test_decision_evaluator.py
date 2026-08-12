import pytest

from models import (
    Candidate,
    Constraint,
    DecisionCase,
    DecisionCriterion,
)
from services.decision_evaluator import (
    evaluate_decision_case,
    validate_decision_case,
)


def test_validate_decision_case_accepts_valid_case():
    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[
            Candidate(name="Qdrant"),
            Candidate(name="Milvus"),
        ],
        criteria=[
            DecisionCriterion(
                name="Reliability",
                weight=0.4,
                source="user",
            )
        ],
    )

    validate_decision_case(decision)


def test_validate_decision_case_requires_question():
    decision = DecisionCase(
        question="   ",
        candidates=[Candidate(name="Qdrant")],
    )

    with pytest.raises(
        ValueError,
        match="decision question must not be empty",
    ):
        validate_decision_case(decision)


def test_validate_decision_case_requires_candidate():
    decision = DecisionCase(
        question="Which vector database should we use?",
    )

    with pytest.raises(
        ValueError,
        match="decision must contain at least one candidate",
    ):
        validate_decision_case(decision)


def test_validate_decision_case_rejects_duplicate_candidate_names():
    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[
            Candidate(name="Qdrant"),
            Candidate(name="qdrant"),
        ],
    )

    with pytest.raises(
        ValueError,
        match="candidate names must be unique",
    ):
        validate_decision_case(decision)


def test_validate_decision_case_rejects_negative_weight():
    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[Candidate(name="Qdrant")],
        criteria=[
            DecisionCriterion(
                name="Reliability",
                weight=-0.1,
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match="weight must be non-negative",
    ):
        validate_decision_case(decision)


def test_hard_constraint_disqualifies_candidate():
    qdrant = Candidate(name="Qdrant")
    milvus = Candidate(name="Milvus")

    self_hosted = Constraint(
        text="Must support self-hosting"
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[qdrant, milvus],
        constraints=[self_hosted],
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

    assert evaluation.status == "complete"

    assert evaluation.eligible_candidate_ids == [
        qdrant.candidate_id
    ]
    assert evaluation.disqualified_candidate_ids == [
        milvus.candidate_id
    ]
    assert evaluation.unresolved_candidate_ids == []

    qdrant_result = evaluation.candidate_results[0]
    milvus_result = evaluation.candidate_results[1]

    assert qdrant_result.status == "eligible"
    assert milvus_result.status == "disqualified"

    assert milvus_result.violated_constraint_ids == [
        self_hosted.constraint_id
    ]


def test_missing_constraint_evidence_keeps_candidate_unresolved():
    qdrant = Candidate(name="Qdrant")

    self_hosted = Constraint(
        text="Must support self-hosting"
    )
    metadata_filtering = Constraint(
        text="Must support metadata filtering"
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[qdrant],
        constraints=[
            self_hosted,
            metadata_filtering,
        ],
    )

    evaluation = evaluate_decision_case(
        decision,
        constraint_results={
            qdrant.candidate_id: {
                self_hosted.constraint_id: True,
            }
        },
    )

    assert evaluation.status == "incomplete"
    assert evaluation.eligible_candidate_ids == []
    assert evaluation.disqualified_candidate_ids == []
    assert evaluation.unresolved_candidate_ids == [
        qdrant.candidate_id
    ]

    result = evaluation.candidate_results[0]

    assert result.status == "unresolved"
    assert result.missing_constraint_ids == [
        metadata_filtering.constraint_id
    ]


def test_known_violation_disqualifies_even_when_other_results_are_missing():
    qdrant = Candidate(name="Qdrant")

    self_hosted = Constraint(
        text="Must support self-hosting"
    )
    metadata_filtering = Constraint(
        text="Must support metadata filtering"
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[qdrant],
        constraints=[
            self_hosted,
            metadata_filtering,
        ],
    )

    evaluation = evaluate_decision_case(
        decision,
        constraint_results={
            qdrant.candidate_id: {
                self_hosted.constraint_id: False,
            }
        },
    )

    result = evaluation.candidate_results[0]

    assert result.status == "disqualified"
    assert result.violated_constraint_ids == [
        self_hosted.constraint_id
    ]
    assert result.missing_constraint_ids == [
        metadata_filtering.constraint_id
    ]


def test_candidates_are_eligible_when_no_hard_constraints_exist():
    qdrant = Candidate(name="Qdrant")
    milvus = Candidate(name="Milvus")

    decision = DecisionCase(
        question="Which vector database should we use?",
        candidates=[qdrant, milvus],
    )

    evaluation = evaluate_decision_case(decision)

    assert evaluation.status == "complete"
    assert evaluation.eligible_candidate_ids == [
        qdrant.candidate_id,
        milvus.candidate_id,
    ]
    assert evaluation.disqualified_candidate_ids == []
    assert evaluation.unresolved_candidate_ids == []
