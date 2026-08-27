"""Controlled activation bridge for prepared decision re-evaluation."""

from __future__ import annotations

from models import (
    ReevaluationPreparation,
    SummaryState,
)
from services.reevaluation_reactivation import (
    apply_reevaluation_reactivation,
)


def activate_prepared_reevaluation(
    state: SummaryState,
    preparation: ReevaluationPreparation,
) -> SummaryState:
    """
    Activate an already-prepared and authorized re-evaluation.

    This bridge only installs the prepared research-analysis projection
    and reopens the existing adaptive orchestration gate.

    It deliberately does NOT:
    - perform retrieval;
    - call an LLM;
    - execute the adaptive loop;
    - reset budget or usage;
    - reset iteration / query / gap history;
    - recompute readiness;
    - create candidate scores;
    - predict a winner;
    - change structured recommendation.
    """

    decision = state.decision_case

    if decision is None:
        raise ValueError(
            "cannot activate reevaluation without decision case"
        )

    decision_id = decision.decision_id

    if preparation.decision_id != decision_id:
        raise ValueError(
            "preparation decision_id does not match state decision"
        )

    if (
        preparation.merged_analysis.decision_id
        != decision_id
    ):
        raise ValueError(
            "prepared analysis decision_id "
            "does not match state decision"
        )

    if (
        preparation.reactivation.decision_id
        != decision_id
    ):
        raise ValueError(
            "prepared reactivation decision_id "
            "does not match state decision"
        )

    adaptive_state = state.adaptive_research_state

    if adaptive_state is None:
        raise ValueError(
            "cannot activate reevaluation "
            "without adaptive research state"
        )

    if adaptive_state.decision_id != decision_id:
        raise ValueError(
            "adaptive state decision_id "
            "does not match state decision"
        )

    reactivation = preparation.reactivation

    # Blocked / unknown preparation must be a complete no-op.
    if (
        reactivation.status != "ELIGIBLE"
        or not reactivation.eligible
        or not reactivation.actionable_gap_ids
    ):
        return state

    reopened_adaptive, reopened_stopping = (
        apply_reevaluation_reactivation(
            reactivation,
            adaptive_state,
            state.stopping_decision,
        )
    )

    # Install the prepared analysis only after all validation and
    # authorization boundaries have passed.
    state.research_analysis = (
        preparation.merged_analysis
    )

    state.adaptive_research_state = (
        reopened_adaptive
    )

    state.stopping_decision = (
        reopened_stopping
    )

    return state
