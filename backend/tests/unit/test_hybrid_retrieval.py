import pytest

from models import (
    Evidence,
    InternalDocument,
)
from services.hybrid_retrieval import (
    hybrid_retrieve,
    internal_hits_to_evidence,
    merge_hybrid_evidence,
    normalize_source_identity,
    retrieve_internal_documents,
)


def make_documents():
    return [
        InternalDocument(
            document_id="doc_architecture",
            title="Vector Database Architecture Decision",
            content=(
                "Our production RAG system runs on Kubernetes. "
                "Operational simplicity and metadata filtering "
                "are important requirements. Qdrant was easier "
                "to operate in our internal deployment."
            ),
            source_type="architecture_document",
            source_path="docs/adr/vector-db.md",
        ),
        InternalDocument(
            document_id="doc_incident",
            title="Milvus Production Incident",
            content=(
                "Historical incident involving Milvus cluster "
                "operations and recovery procedures."
            ),
            source_type="historical_incident",
            source_path="incidents/milvus.md",
        ),
        InternalDocument(
            document_id="doc_unrelated",
            title="Frontend Design Guide",
            content=(
                "Design standards for buttons and typography."
            ),
        ),
    ]


def make_external(
    *,
    evidence_id="evi_external",
    url="https://qdrant.tech/documentation/",
    rank=1,
):
    return Evidence(
        evidence_id=evidence_id,
        task_id=1,
        trace_id="trace_test",
        query="Qdrant Kubernetes operations",
        backend="web",
        source_title="Qdrant Documentation",
        source_url=url,
        snippet="Official Qdrant documentation.",
        content="Kubernetes deployment documentation.",
        source_rank=rank,
    )


def test_internal_retrieval_ranks_relevant_document():
    documents = make_documents()

    hits = retrieve_internal_documents(
        "Kubernetes operational simplicity Qdrant",
        documents,
        top_k=2,
    )

    assert hits
    assert hits[0].document_id == "doc_architecture"

    assert "kubernetes" in hits[0].matched_terms
    assert "qdrant" in hits[0].matched_terms


def test_internal_retrieval_excludes_unmatched_documents():
    documents = make_documents()

    hits = retrieve_internal_documents(
        "Milvus recovery incident",
        documents,
    )

    ids = [
        hit.document_id
        for hit in hits
    ]

    assert "doc_incident" in ids
    assert "doc_unrelated" not in ids


def test_internal_hit_converts_to_existing_evidence_model():
    documents = make_documents()

    hits = retrieve_internal_documents(
        "Kubernetes Qdrant",
        documents,
        top_k=1,
    )

    evidence_items = internal_hits_to_evidence(
        "Kubernetes Qdrant",
        documents,
        hits,
        task_id=10,
        trace_id="trace_internal",
    )

    assert len(evidence_items) == 1

    evidence = evidence_items[0]

    assert evidence.backend == "internal"
    assert evidence.task_id == 10
    assert evidence.trace_id == "trace_internal"

    assert evidence.source_url == (
        "internal://doc_architecture"
    )

    assert evidence.source_rank == 1


def test_internal_evidence_keeps_full_document_content():
    documents = make_documents()

    hits = retrieve_internal_documents(
        "Qdrant",
        documents,
        top_k=1,
    )

    evidence = internal_hits_to_evidence(
        "Qdrant",
        documents,
        hits,
        task_id=1,
        trace_id="trace_test",
    )[0]

    assert (
        evidence.content
        == documents[0].content
    )


def test_source_identity_removes_url_fragment():
    first = make_external(
        url=(
            "https://qdrant.tech/documentation/"
            "#deployment"
        ),
    )

    second = make_external(
        evidence_id="evi_second",
        url="https://qdrant.tech/documentation",
    )

    assert (
        normalize_source_identity(first)
        == normalize_source_identity(second)
    )


def test_hybrid_merge_preserves_internal_and_external_evidence():
    internal = Evidence(
        task_id=1,
        trace_id="trace_test",
        query="vector database",
        backend="internal",
        source_title="Internal ADR",
        source_url="internal://doc_1",
        content="Internal benchmark.",
        source_rank=1,
    )

    external = make_external(
        rank=1,
    )

    result = merge_hybrid_evidence(
        "vector database",
        external_evidence=[external],
        internal_evidence=[internal],
    )

    assert len(result.evidence_items) == 2
    assert result.internal_count == 1
    assert result.external_count == 1
    assert result.duplicate_count == 0


def test_hybrid_merge_deduplicates_same_external_source():
    first = make_external(
        evidence_id="evi_first",
        url="https://qdrant.tech/documentation/",
        rank=1,
    )

    second = make_external(
        evidence_id="evi_second",
        url="https://qdrant.tech/documentation",
        rank=2,
    )

    result = merge_hybrid_evidence(
        "Qdrant",
        external_evidence=[
            first,
            second,
        ],
        internal_evidence=[],
    )

    assert len(result.evidence_items) == 1
    assert result.duplicate_count == 1


def test_hybrid_retrieve_runs_internal_and_external_pipeline():
    documents = make_documents()

    external = make_external()

    result = hybrid_retrieve(
        "Kubernetes operational simplicity Qdrant",
        documents=documents,
        external_evidence=[external],
        task_id=5,
        trace_id="trace_hybrid",
        internal_top_k=2,
    )

    assert result.internal_count >= 1
    assert result.external_count == 1

    assert any(
        evidence.backend == "internal"
        for evidence in result.evidence_items
    )

    assert any(
        evidence.backend == "web"
        for evidence in result.evidence_items
    )


def test_hybrid_result_can_be_capped():
    documents = make_documents()

    external = [
        make_external(
            evidence_id="evi_one",
            url="https://example.com/one",
            rank=1,
        ),
        make_external(
            evidence_id="evi_two",
            url="https://example.com/two",
            rank=2,
        ),
    ]

    result = hybrid_retrieve(
        "Kubernetes Qdrant Milvus",
        documents=documents,
        external_evidence=external,
        task_id=1,
        trace_id="trace_test",
        max_results=2,
    )

    assert len(result.evidence_items) == 2


def test_negative_max_results_is_rejected():
    with pytest.raises(
        ValueError,
        match="max_results must be non-negative",
    ):
        merge_hybrid_evidence(
            "test",
            external_evidence=[],
            internal_evidence=[],
            max_results=-1,
        )


def test_zero_top_k_returns_no_internal_hits():
    documents = make_documents()

    hits = retrieve_internal_documents(
        "Qdrant",
        documents,
        top_k=0,
    )

    assert hits == []
