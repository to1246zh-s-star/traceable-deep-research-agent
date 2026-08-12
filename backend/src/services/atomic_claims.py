"""Atomic claim extraction and grounding baseline for V3 Phase 10."""

import re

from models import AtomicClaim, Claim


VALID_GROUNDING_STATUSES = {
    "grounded",
    "ungrounded",
}


def split_claim_text(text: str) -> list[str]:
    """
    Deterministically split a task-level Claim into atomic claim candidates.

    Phase 10 baseline intentionally uses conservative sentence-level
    segmentation rather than LLM extraction. Semantic claim extraction
    can be introduced later without changing the AtomicClaim domain model.
    """

    normalized = " ".join(text.split())

    if not normalized:
        return []

    parts = re.split(
        r"(?<=[.!?])\s+(?=[A-Z0-9])",
        normalized,
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def create_atomic_claims(
    claim: Claim,
    *,
    evidence_map: dict[int, list[str]] | None = None,
) -> list[AtomicClaim]:
    """
    Convert one V2 task-level Claim into AtomicClaim objects.

    evidence_map maps sentence index -> evidence IDs.

    Example:
        {
            0: ["evi_abc"],
            1: ["evi_xyz", "evi_123"],
        }

    Evidence is never automatically copied from the parent Claim because
    task-level grounding does not prove that every Evidence item supports
    every atomic factual statement.
    """

    fragments = split_claim_text(claim.text)

    evidence_map = evidence_map or {}

    atomic_claims: list[AtomicClaim] = []

    for index, fragment in enumerate(fragments):
        evidence_ids = list(
            dict.fromkeys(
                evidence_map.get(index, [])
            )
        )

        unknown_evidence_ids = [
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in claim.evidence_ids
        ]

        if unknown_evidence_ids:
            raise ValueError(
                "atomic claim evidence must belong to parent claim: "
                + ", ".join(unknown_evidence_ids)
            )

        grounding_status = (
            "grounded"
            if evidence_ids
            else "ungrounded"
        )

        atomic_claims.append(
            AtomicClaim(
                parent_claim_id=claim.claim_id,
                task_id=claim.task_id,
                trace_id=claim.trace_id,
                text=fragment,
                evidence_ids=evidence_ids,
                grounding_status=grounding_status,
            )
        )

    return atomic_claims


def validate_atomic_claim(
    atomic_claim: AtomicClaim,
    parent_claim: Claim,
) -> None:
    """Validate provenance between an AtomicClaim and its parent V2 Claim."""

    errors: list[str] = []

    if atomic_claim.parent_claim_id != parent_claim.claim_id:
        errors.append(
            "atomic claim parent_claim_id does not match parent claim"
        )

    if atomic_claim.task_id != parent_claim.task_id:
        errors.append(
            "atomic claim task_id does not match parent claim"
        )

    if atomic_claim.trace_id != parent_claim.trace_id:
        errors.append(
            "atomic claim trace_id does not match parent claim"
        )

    if not atomic_claim.text.strip():
        errors.append(
            "atomic claim text must not be empty"
        )

    unknown_evidence_ids = [
        evidence_id
        for evidence_id in atomic_claim.evidence_ids
        if evidence_id not in parent_claim.evidence_ids
    ]

    if unknown_evidence_ids:
        errors.append(
            "atomic claim contains evidence not present in parent claim"
        )

    expected_status = (
        "grounded"
        if atomic_claim.evidence_ids
        else "ungrounded"
    )

    if atomic_claim.grounding_status != expected_status:
        errors.append(
            "atomic claim grounding_status is inconsistent with evidence"
        )

    if atomic_claim.grounding_status not in VALID_GROUNDING_STATUSES:
        errors.append(
            f"invalid grounding status {atomic_claim.grounding_status!r}"
        )

    if errors:
        raise ValueError("; ".join(errors))
