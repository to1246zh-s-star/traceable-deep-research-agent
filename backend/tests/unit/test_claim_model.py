from datetime import datetime

from models import Claim, SummaryState


def test_claim_model_preserves_traceable_evidence_links():
    claim = Claim(
        task_id=2,
        trace_id="trace_test123",
        text="RAG combines retrieval with generation.",
        evidence_ids=["evi_a", "evi_b"],
    )

    assert claim.claim_id.startswith("clm_")
    assert claim.task_id == 2
    assert claim.trace_id == "trace_test123"
    assert claim.text == "RAG combines retrieval with generation."
    assert claim.evidence_ids == ["evi_a", "evi_b"]

    datetime.fromisoformat(claim.created_at)


def test_claim_evidence_ids_default_to_independent_lists():
    first = Claim(
        task_id=1,
        trace_id="trace_one",
        text="First claim",
    )
    second = Claim(
        task_id=2,
        trace_id="trace_two",
        text="Second claim",
    )

    first.evidence_ids.append("evi_test")

    assert first.evidence_ids == ["evi_test"]
    assert second.evidence_ids == []


def test_summary_state_stores_claims_independently():
    state = SummaryState(research_topic="RAG")

    claim = Claim(
        task_id=1,
        trace_id="trace_test",
        text="Traceable claim",
    )

    state.claims.append(claim)

    assert len(state.claims) == 1
    assert state.claims[0] is claim

    another_state = SummaryState(research_topic="Other")

    assert another_state.claims == []
