"""Incremental reuse of semantic evidence signals."""

from __future__ import annotations

from models import EvidenceSignal
from services.decision_input_builder import (
    LEXICAL_SIGNAL_RATIONALE,
)


SignalKey = tuple[str, str, str]


def signal_key(
    signal: EvidenceSignal,
) -> SignalKey:
    """Return the stable semantic identity of one evidence signal."""

    return (
        signal.evidence_id,
        signal.candidate_id,
        signal.criterion_id,
    )


def is_semantically_interpreted(
    signal: EvidenceSignal,
) -> bool:
    """
    Return whether a signal contains a completed semantic interpretation.

    Raw lexical proposals and semantic-extraction fallbacks retain the
    deterministic lexical rationale. They must remain eligible for a future
    retry rather than being cached as completed LLM work.
    """

    return (
        signal.rationale
        != LEXICAL_SIGNAL_RATIONALE
    )


def partition_semantic_proposals(
    proposals: list[EvidenceSignal],
    existing_signals: list[EvidenceSignal],
) -> tuple[
    dict[SignalKey, EvidenceSignal],
    list[EvidenceSignal],
]:
    """
    Partition proposals into reusable semantic results and pending work.

    Only previously completed semantic interpretations are reusable.
    """

    proposal_keys = {
        signal_key(proposal)
        for proposal in proposals
    }

    reusable = {
        signal_key(signal): signal
        for signal in existing_signals
        if (
            signal_key(signal) in proposal_keys
            and is_semantically_interpreted(signal)
        )
    }

    pending = [
        proposal
        for proposal in proposals
        if signal_key(proposal) not in reusable
    ]

    return reusable, pending


def merge_semantic_signals(
    proposals: list[EvidenceSignal],
    reusable: dict[
        SignalKey,
        EvidenceSignal,
    ],
    newly_interpreted: list[EvidenceSignal],
) -> list[EvidenceSignal]:
    """
    Merge cached and newly interpreted results in current proposal order.

    Deterministic fields such as source confidence and applicability always
    come from the freshly rebuilt proposal. Only semantic direction,
    semantic strength, and rationale are reused from prior interpretations.
    """

    new_by_key = {
        signal_key(signal): signal
        for signal in newly_interpreted
    }

    merged: list[EvidenceSignal] = []

    for proposal in proposals:
        key = signal_key(proposal)

        semantic = new_by_key.get(key)

        if semantic is None:
            semantic = reusable.get(key)

        if semantic is None:
            # No completed semantic interpretation. Preserve conservative
            # lexical proposal.
            merged.append(proposal)
            continue

        merged.append(
            EvidenceSignal(
                signal_id=proposal.signal_id,
                evidence_id=proposal.evidence_id,
                candidate_id=proposal.candidate_id,
                criterion_id=proposal.criterion_id,
                direction=semantic.direction,
                strength=semantic.strength,
                source_confidence=proposal.source_confidence,
                applicability=proposal.applicability,
                atomic_claim_id=proposal.atomic_claim_id,
                rationale=semantic.rationale,
            )
        )

    return merged
