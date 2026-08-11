from models import Claim, Evidence, ExecutionTrace, SummaryState
from services.research_store import SQLiteResearchStore


def test_sqlite_store_persists_evidence_and_claims(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")

    trace = ExecutionTrace(
        trace_id="trace_evidence_test",
        task_id=1,
        status="completed",
    )

    evidence = Evidence(
        evidence_id="evi_test",
        task_id=1,
        trace_id=trace.trace_id,
        query="What is RAG?",
        backend="tavily",
        source_title="RAG source",
        source_url="https://example.com/rag",
        snippet="RAG combines retrieval and generation.",
        content="Full RAG source content.",
        source_rank=1,
    )

    claim = Claim(
        claim_id="clm_test",
        task_id=1,
        trace_id=trace.trace_id,
        text="RAG combines retrieval with language generation.",
        evidence_ids=[evidence.evidence_id],
    )

    state = SummaryState(
        research_topic="RAG",
        execution_traces=[trace],
        evidence_items=[evidence],
        claims=[claim],
    )

    research_id = store.save(state)

    restored = store.get(research_id)

    assert restored is not None

    assert len(restored.evidence_items) == 1
    assert len(restored.claims) == 1

    restored_evidence = restored.evidence_items[0]
    restored_claim = restored.claims[0]

    assert restored_evidence.evidence_id == evidence.evidence_id
    assert restored_evidence.trace_id == trace.trace_id
    assert restored_evidence.source_url == "https://example.com/rag"
    assert restored_evidence.snippet == (
        "RAG combines retrieval and generation."
    )
    assert restored_evidence.content == "Full RAG source content."

    assert restored_claim.claim_id == claim.claim_id
    assert restored_claim.trace_id == trace.trace_id
    assert restored_claim.evidence_ids == [evidence.evidence_id]
