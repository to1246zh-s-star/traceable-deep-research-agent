"""Deterministic claim novelty and decision-relevant information gain."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from models import (
    AdaptiveResearchIteration,
    Claim,
    EvidenceSignal,
)


@dataclass(kw_only=True)
class ClaimInformationSnapshot:
    claim_signatures: set[str] = field(default_factory=set)
    directional_signal_keys: set[str] = field(default_factory=set)
    covered_pairs: set[str] = field(default_factory=set)


def capture_claim_information_snapshot(
    claims: list[Claim],
    signals: list[EvidenceSignal],
) -> ClaimInformationSnapshot:
    claim_signatures = {
        signature
        for claim in claims
        if (
            signature := claim_signature(
                claim
            )
        )
    }

    directional_signal_keys: set[str] = set()
    covered_pairs: set[str] = set()

    for signal in signals:
        direction = str(
            signal.direction
            or ""
        ).strip().upper()

        if direction not in {
            "POSITIVE",
            "NEGATIVE",
        }:
            continue

        pair_key = candidate_criterion_key(
            signal.candidate_id,
            signal.criterion_id,
        )

        covered_pairs.add(
            pair_key
        )

        directional_signal_keys.add(
            directional_signal_key(
                signal
            )
        )

    return ClaimInformationSnapshot(
        claim_signatures=claim_signatures,
        directional_signal_keys=directional_signal_keys,
        covered_pairs=covered_pairs,
    )


def assess_iteration_information_gain(
    iteration: AdaptiveResearchIteration,
    before: ClaimInformationSnapshot,
    after: ClaimInformationSnapshot,
    *,
    before_claim_count: int,
    after_claim_count: int,
) -> str:
    """
    Attach deterministic Phase-31 information-gain metadata.

    Information gain measures novelty in decision-relevant knowledge state.
    It does not assess factual correctness or candidate quality.
    """

    iteration_status = getattr(
        iteration,
        "status",
        None,
    )

    if iteration_status != "completed":
        return _set_unknown(
            iteration,
            "iteration_not_completed_or_unobservable",
        )

    new_claim_count = max(
        0,
        after_claim_count - before_claim_count,
    )

    novel_claim_signatures = (
        after.claim_signatures
        - before.claim_signatures
    )

    novel_claim_count = len(
        novel_claim_signatures
    )

    duplicate_claim_count = max(
        0,
        new_claim_count - novel_claim_count,
    )

    claim_novelty_ratio = (
        novel_claim_count / new_claim_count
        if new_claim_count > 0
        else 0.0
    )

    new_directional_signals = (
        after.directional_signal_keys
        - before.directional_signal_keys
    )

    new_pairs = sorted(
        after.covered_pairs
        - before.covered_pairs
    )

    iteration.new_claim_count = (
        new_claim_count
    )

    iteration.novel_claim_count = (
        novel_claim_count
    )

    iteration.duplicate_claim_count = (
        duplicate_claim_count
    )

    iteration.claim_novelty_ratio = round(
        claim_novelty_ratio,
        4,
    )

    iteration.new_directional_signal_count = len(
        new_directional_signals
    )

    iteration.new_candidate_criterion_pairs = (
        new_pairs
    )

    reasons: list[str] = []

    if new_claim_count:
        reasons.append(
            f"{new_claim_count} new claim(s)"
        )

    if novel_claim_count:
        reasons.append(
            f"{novel_claim_count} lexically novel claim(s)"
        )

    if new_directional_signals:
        reasons.append(
            f"{len(new_directional_signals)} "
            "new directional evidence signal(s)"
        )

    if new_pairs:
        reasons.append(
            f"{len(new_pairs)} newly covered "
            "candidate×criterion pair(s)"
        )

    # Strongest decision-relevant gain: genuinely new pair coverage.
    if (
        new_pairs
        and new_directional_signals
    ):
        status = "HIGH_INFORMATION_GAIN"

    # New directional evidence or strongly novel claim set.
    elif (
        new_directional_signals
        or (
            novel_claim_count >= 2
            and claim_novelty_ratio >= 0.5
        )
    ):
        status = "MODERATE_INFORMATION_GAIN"

    # New claims exist but mostly repeat existing knowledge.
    elif new_claim_count > 0:
        status = "LOW_INFORMATION_GAIN"

        if novel_claim_count == 0:
            reasons.append(
                "new claims repeat existing claim signatures"
            )
        else:
            reasons.append(
                "new claims add limited decision-state novelty"
            )

    else:
        status = "NO_INFORMATION_GAIN"
        reasons.append(
            "no new claims or directional decision signals"
        )

    iteration.information_gain_status = (
        status
    )

    iteration.information_gain_reasons = (
        reasons
    )

    return status


def claim_signature(
    claim: Claim,
) -> str:
    text = _claim_text(
        claim
    )

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        text.casefold(),
    )

    return " ".join(
        token
        for token in normalized.split()
        if len(token) >= 2
    )


def candidate_criterion_key(
    candidate_id: str,
    criterion_id: str,
) -> str:
    return (
        f"{candidate_id}|"
        f"{criterion_id}"
    )


def directional_signal_key(
    signal: EvidenceSignal,
) -> str:
    return "|".join([
        str(signal.evidence_id),
        str(signal.candidate_id),
        str(signal.criterion_id),
        str(signal.direction).upper(),
    ])


def enrich_retrieval_yield_with_information_gain(
    iteration: AdaptiveResearchIteration,
) -> None:
    status = (
        iteration.information_gain_status
        or "UNKNOWN"
    )

    if status == "UNKNOWN":
        return

    message = (
        "decision information gain: "
        f"{status.lower()}"
    )

    if (
        message
        not in iteration.retrieval_yield_reasons
    ):
        iteration.retrieval_yield_reasons.append(
            message
        )


def _claim_text(
    claim: Claim,
) -> str:
    for name in (
        "text",
        "claim_text",
        "statement",
        "content",
    ):
        value = getattr(
            claim,
            name,
            None,
        )

        if value:
            return str(value)

    return ""


def _set_unknown(
    iteration: AdaptiveResearchIteration,
    reason: str,
) -> str:
    iteration.information_gain_status = "UNKNOWN"
    iteration.new_claim_count = 0
    iteration.novel_claim_count = 0
    iteration.duplicate_claim_count = 0
    iteration.claim_novelty_ratio = 0.0
    iteration.new_directional_signal_count = 0
    iteration.new_candidate_criterion_pairs = []
    iteration.information_gain_reasons = [
        reason
    ]

    return "UNKNOWN"
