import pytest

from models import AtomicClaim, Claim
from services.atomic_claims import (
    create_atomic_claims,
    split_claim_text,
    validate_atomic_claim,
)


def make_parent_claim():
    return Claim(
        task_id=1,
        trace_id="trace_test",
        text=(
            "Qdrant supports metadata filtering. "
            "Qdrant provides Kubernetes deployment documentation."
        ),
        evidence_ids=[
            "evi_filter",
            "evi_kubernetes",
        ],
    )


def test_split_claim_text_into_atomic_sentences():
    fragments = split_claim_text(
        "Qdrant supports filtering. "
        "Milvus supports distributed deployment."
    )

    assert fragments == [
        "Qdrant supports filtering.",
        "Milvus supports distributed deployment.",
    ]


def test_empty_claim_text_produces_no_atomic_claims():
    assert split_claim_text("   ") == []


def test_create_atomic_claims_preserves_parent_provenance():
    parent = make_parent_claim()

    atomic_claims = create_atomic_claims(parent)

    assert len(atomic_claims) == 2

    for atomic_claim in atomic_claims:
        assert atomic_claim.atomic_claim_id.startswith("aclm_")
        assert atomic_claim.parent_claim_id == parent.claim_id
        assert atomic_claim.task_id == parent.task_id
        assert atomic_claim.trace_id == parent.trace_id


def test_atomic_claims_are_not_automatically_grounded():
    parent = make_parent_claim()

    atomic_claims = create_atomic_claims(parent)

    assert atomic_claims[0].evidence_ids == []
    assert atomic_claims[1].evidence_ids == []

    assert atomic_claims[0].grounding_status == "ungrounded"
    assert atomic_claims[1].grounding_status == "ungrounded"


def test_explicit_evidence_mapping_grounds_atomic_claims():
    parent = make_parent_claim()

    atomic_claims = create_atomic_claims(
        parent,
        evidence_map={
            0: ["evi_filter"],
            1: ["evi_kubernetes"],
        },
    )

    assert atomic_claims[0].evidence_ids == [
        "evi_filter"
    ]
    assert atomic_claims[1].evidence_ids == [
        "evi_kubernetes"
    ]

    assert atomic_claims[0].grounding_status == "grounded"
    assert atomic_claims[1].grounding_status == "grounded"


def test_multiple_evidence_items_can_support_one_atomic_claim():
    parent = make_parent_claim()

    atomic_claims = create_atomic_claims(
        parent,
        evidence_map={
            0: [
                "evi_filter",
                "evi_kubernetes",
            ],
        },
    )

    assert atomic_claims[0].evidence_ids == [
        "evi_filter",
        "evi_kubernetes",
    ]


def test_duplicate_evidence_ids_are_deduplicated():
    parent = make_parent_claim()

    atomic_claims = create_atomic_claims(
        parent,
        evidence_map={
            0: [
                "evi_filter",
                "evi_filter",
            ],
        },
    )

    assert atomic_claims[0].evidence_ids == [
        "evi_filter"
    ]


def test_atomic_claim_cannot_reference_evidence_outside_parent_claim():
    parent = make_parent_claim()

    with pytest.raises(
        ValueError,
        match="evidence must belong to parent claim",
    ):
        create_atomic_claims(
            parent,
            evidence_map={
                0: ["evi_unknown"],
            },
        )


def test_validate_atomic_claim_accepts_valid_grounded_claim():
    parent = make_parent_claim()

    atomic_claim = AtomicClaim(
        parent_claim_id=parent.claim_id,
        task_id=parent.task_id,
        trace_id=parent.trace_id,
        text="Qdrant supports metadata filtering.",
        evidence_ids=["evi_filter"],
        grounding_status="grounded",
    )

    validate_atomic_claim(
        atomic_claim,
        parent,
    )


def test_validate_atomic_claim_detects_wrong_parent():
    parent = make_parent_claim()

    atomic_claim = AtomicClaim(
        parent_claim_id="clm_wrong",
        task_id=parent.task_id,
        trace_id=parent.trace_id,
        text="Qdrant supports metadata filtering.",
    )

    with pytest.raises(
        ValueError,
        match="parent_claim_id",
    ):
        validate_atomic_claim(
            atomic_claim,
            parent,
        )


def test_validate_atomic_claim_detects_inconsistent_grounding_status():
    parent = make_parent_claim()

    atomic_claim = AtomicClaim(
        parent_claim_id=parent.claim_id,
        task_id=parent.task_id,
        trace_id=parent.trace_id,
        text="Qdrant supports metadata filtering.",
        evidence_ids=["evi_filter"],
        grounding_status="ungrounded",
    )

    with pytest.raises(
        ValueError,
        match="grounding_status",
    ):
        validate_atomic_claim(
            atomic_claim,
            parent,
        )


def test_v2_claim_model_remains_unchanged_and_usable():
    claim = Claim(
        task_id=42,
        trace_id="trace_v2",
        text="Legacy task-level claim.",
        evidence_ids=["evi_legacy"],
    )

    assert claim.claim_id.startswith("clm_")
    assert claim.task_id == 42
    assert claim.trace_id == "trace_v2"
    assert claim.text == "Legacy task-level claim."
    assert claim.evidence_ids == ["evi_legacy"]
