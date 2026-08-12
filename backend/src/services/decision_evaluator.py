"""Deterministic baseline evaluation for V3 technical decisions."""

from models import (
    CandidateDecisionResult,
    DecisionCase,
    DecisionEvaluation,
)


VALID_SOURCES = {"user", "agent"}


def validate_decision_case(decision: DecisionCase) -> None:
    """Validate the minimum structural rules required for evaluation."""

    errors: list[str] = []

    if not decision.question.strip():
        errors.append("decision question must not be empty")

    if not decision.candidates:
        errors.append("decision must contain at least one candidate")

    candidate_ids = [candidate.candidate_id for candidate in decision.candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("candidate IDs must be unique")

    normalized_names = [
        candidate.name.strip().lower()
        for candidate in decision.candidates
        if candidate.name.strip()
    ]

    if any(not candidate.name.strip() for candidate in decision.candidates):
        errors.append("candidate name must not be empty")

    if len(normalized_names) != len(set(normalized_names)):
        errors.append("candidate names must be unique")

    for requirement in decision.requirements:
        if not requirement.text.strip():
            errors.append(
                f"requirement {requirement.requirement_id} text must not be empty"
            )

    for constraint in decision.constraints:
        if not constraint.text.strip():
            errors.append(
                f"constraint {constraint.constraint_id} text must not be empty"
            )

        if constraint.source not in VALID_SOURCES:
            errors.append(
                f"constraint {constraint.constraint_id} has invalid source "
                f"{constraint.source!r}"
            )

    for criterion in decision.criteria:
        if not criterion.name.strip():
            errors.append(
                f"criterion {criterion.criterion_id} name must not be empty"
            )

        if criterion.weight < 0:
            errors.append(
                f"criterion {criterion.criterion_id} weight must be non-negative"
            )

        if criterion.source not in VALID_SOURCES:
            errors.append(
                f"criterion {criterion.criterion_id} has invalid source "
                f"{criterion.source!r}"
            )

    if errors:
        raise ValueError("; ".join(errors))


def evaluate_decision_case(
    decision: DecisionCase,
    *,
    constraint_results: dict[str, dict[str, bool]] | None = None,
) -> DecisionEvaluation:
    """
    Evaluate candidate eligibility against hard constraints.

    constraint_results structure:

        {
            candidate_id: {
                constraint_id: True | False
            }
        }

    Missing constraint results are never guessed. A candidate remains
    unresolved until every non-violated hard constraint has a known result.
    """

    validate_decision_case(decision)

    constraint_results = constraint_results or {}

    candidate_results: list[CandidateDecisionResult] = []
    eligible_candidate_ids: list[str] = []
    disqualified_candidate_ids: list[str] = []
    unresolved_candidate_ids: list[str] = []

    constraint_ids = [
        constraint.constraint_id
        for constraint in decision.constraints
    ]

    for candidate in decision.candidates:
        candidate_constraints = constraint_results.get(
            candidate.candidate_id,
            {},
        )

        violated = [
            constraint_id
            for constraint_id in constraint_ids
            if candidate_constraints.get(constraint_id) is False
        ]

        missing = [
            constraint_id
            for constraint_id in constraint_ids
            if constraint_id not in candidate_constraints
        ]

        if violated:
            status = "disqualified"
            disqualified_candidate_ids.append(candidate.candidate_id)

        elif missing:
            status = "unresolved"
            unresolved_candidate_ids.append(candidate.candidate_id)

        else:
            status = "eligible"
            eligible_candidate_ids.append(candidate.candidate_id)

        candidate_results.append(
            CandidateDecisionResult(
                candidate_id=candidate.candidate_id,
                status=status,
                violated_constraint_ids=violated,
                missing_constraint_ids=missing,
            )
        )

    evaluation_status = (
        "incomplete"
        if unresolved_candidate_ids
        else "complete"
    )

    return DecisionEvaluation(
        decision_id=decision.decision_id,
        status=evaluation_status,
        candidate_results=candidate_results,
        eligible_candidate_ids=eligible_candidate_ids,
        disqualified_candidate_ids=disqualified_candidate_ids,
        unresolved_candidate_ids=unresolved_candidate_ids,
    )
