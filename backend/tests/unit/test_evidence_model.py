from datetime import datetime

from models import Evidence, SummaryState


def test_evidence_model_generates_identity_and_preserves_provenance():
    evidence = Evidence(
        task_id=2,
        trace_id="trace_test123",
        query="what is retrieval augmented generation",
        backend="tavily",
        source_title="RAG overview",
        source_url="https://example.com/rag",
        snippet="Retrieval-augmented generation combines retrieval with generation.",
        content="Full source content.",
        source_rank=1,
    )

    assert evidence.evidence_id.startswith("evi_")
    assert evidence.task_id == 2
    assert evidence.trace_id == "trace_test123"
    assert evidence.query == "what is retrieval augmented generation"
    assert evidence.backend == "tavily"

    assert evidence.source_title == "RAG overview"
    assert evidence.source_url == "https://example.com/rag"
    assert evidence.snippet is not None
    assert evidence.content == "Full source content."
    assert evidence.source_rank == 1

    datetime.fromisoformat(evidence.created_at)


def test_evidence_optional_source_fields_default_to_none():
    evidence = Evidence(
        task_id=1,
        trace_id="trace_test456",
        query="test query",
        backend="duckduckgo",
    )

    assert evidence.source_title is None
    assert evidence.source_url is None
    assert evidence.snippet is None
    assert evidence.content is None
    assert evidence.source_rank is None


def test_summary_state_stores_evidence_items_independently():
    state = SummaryState(research_topic="RAG")

    evidence = Evidence(
        task_id=1,
        trace_id="trace_test789",
        query="RAG architecture",
        backend="tavily",
    )

    state.evidence_items.append(evidence)

    assert len(state.evidence_items) == 1
    assert state.evidence_items[0] is evidence

    another_state = SummaryState(research_topic="Another topic")

    assert another_state.evidence_items == []
