from dataclasses import asdict

from models import (
    Candidate,
    Constraint,
    DecisionCase,
    DecisionCriterion,
    Requirement,
)


def test_candidate_has_generated_identity():
    candidate = Candidate(name="Qdrant")

    assert candidate.candidate_id.startswith("cand_")
    assert candidate.name == "Qdrant"
    assert candidate.description is None


def test_requirement_has_generated_identity():
    requirement = Requirement(text="Minimize operational complexity")

    assert requirement.requirement_id.startswith("req_")
    assert requirement.text == "Minimize operational complexity"


def test_constraint_represents_hard_requirement():
    constraint = Constraint(text="Must support self-hosting")

    assert constraint.constraint_id.startswith("con_")
    assert constraint.text == "Must support self-hosting"
    assert constraint.source == "user"


def test_decision_criterion_preserves_weight_and_source():
    criterion = DecisionCriterion(
        name="Reliability",
        weight=0.3,
        source="user",
        description="Production reliability and operational stability",
    )

    assert criterion.criterion_id.startswith("crit_")
    assert criterion.name == "Reliability"
    assert criterion.weight == 0.3
    assert criterion.source == "user"


def test_decision_case_contains_structured_decision_context():
    candidate = Candidate(name="Qdrant")
    requirement = Requirement(text="Use Kubernetes")
    constraint = Constraint(text="Must support self-hosting")
    criterion = DecisionCriterion(
        name="Operational simplicity",
        weight=0.4,
        source="user",
    )

    decision = DecisionCase(
        question="Which vector database should we use?",
        context="Production RAG system with about five million documents",
        candidates=[candidate],
        requirements=[requirement],
        constraints=[constraint],
        criteria=[criterion],
    )

    assert decision.decision_id.startswith("dec_")
    assert decision.status == "draft"
    assert decision.recommendation is None

    assert decision.candidates == [candidate]
    assert decision.requirements == [requirement]
    assert decision.constraints == [constraint]
    assert decision.criteria == [criterion]

    serialized = asdict(decision)

    assert serialized["question"] == "Which vector database should we use?"
    assert serialized["candidates"][0]["name"] == "Qdrant"
    assert serialized["criteria"][0]["weight"] == 0.4


def test_decision_case_collection_defaults_are_isolated():
    first = DecisionCase(question="Decision one")
    second = DecisionCase(question="Decision two")

    first.candidates.append(Candidate(name="Qdrant"))

    assert len(first.candidates) == 1
    assert second.candidates == []


def test_decision_model_ids_are_unique():
    first_candidate = Candidate(name="Qdrant")
    second_candidate = Candidate(name="Milvus")

    first_decision = DecisionCase(question="Decision one")
    second_decision = DecisionCase(question="Decision two")

    assert first_candidate.candidate_id != second_candidate.candidate_id
    assert first_decision.decision_id != second_decision.decision_id
