from fastapi.testclient import TestClient

from main import create_app
from models import (
    Claim,
    Evidence,
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceQuality,
    ExecutionTrace,
    SourceQuality,
    SummaryState,
)


class FakeResearchStore:
    def __init__(self, state):
        self.state = state

    def get(self, research_id):
        if research_id == "research_test":
            return self.state
        return None


def build_state():
    trace = ExecutionTrace(
        trace_id="trace_test",
        task_id=1,
        status="completed",
    )

    evidence = Evidence(
        evidence_id="evi_test",
        task_id=1,
        trace_id=trace.trace_id,
        query="RAG query",
        backend="tavily",
        source_title="RAG source",
        source_url="https://example.com/rag",
        snippet="RAG evidence",
        content="Full RAG evidence",
        source_rank=1,
    )

    claim = Claim(
        claim_id="clm_test",
        task_id=1,
        trace_id=trace.trace_id,
        text="RAG uses retrieved evidence.",
        evidence_ids=[evidence.evidence_id],
    )

    return SummaryState(
        research_topic="RAG",
        execution_traces=[trace],
        evidence_items=[evidence],
        claims=[claim],
        evidence_assessments=[
            EvidenceAssessment(
                evidence_id=evidence.evidence_id,
                decision_id="dec_test",
                source_quality=SourceQuality(
                    evidence_id=evidence.evidence_id,
                    source_type="official_docs",
                    confidence=0.95,
                    authority_type="OFFICIAL_DOCUMENTATION",
                    authority_level="HIGH",
                ),
                evidence_quality=EvidenceQuality(
                    evidence_id=evidence.evidence_id,
                    quality_score=0.9,
                    completeness=0.8,
                ),
                applicability=EvidenceApplicability(
                    evidence_id=evidence.evidence_id,
                    decision_id="dec_test",
                    applicability_score=0.85,
                ),
                overall_score=0.88,
            )
        ],
    )


def build_client(state=None):
    app = create_app()
    app.state.research_store = FakeResearchStore(state or build_state())
    return TestClient(app)


def test_list_research_evidence():
    client = build_client()

    response = client.get("/research/research_test/evidence")

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == "research_test"
    assert len(payload["evidence"]) == 1

    evidence = payload["evidence"][0]

    assert evidence["evidence_id"] == "evi_test"
    assert evidence["trace_id"] == "trace_test"
    assert evidence["source_rank"] == 1
    assert evidence["source_type"] == "official_docs"
    assert evidence["authority_type"] == "OFFICIAL_DOCUMENTATION"
    assert evidence["authority_level"] == "HIGH"


def test_get_research_evidence():
    client = build_client()

    response = client.get(
        "/research/research_test/evidence/evi_test"
    )

    assert response.status_code == 200
    assert response.json()["evidence"]["source_url"] == (
        "https://example.com/rag"
    )


def test_list_research_claims():
    client = build_client()

    response = client.get("/research/research_test/claims")

    assert response.status_code == 200

    claims = response.json()["claims"]

    assert len(claims) == 1
    assert claims[0]["claim_id"] == "clm_test"
    assert claims[0]["evidence_ids"] == ["evi_test"]


def test_get_research_claim_resolves_supporting_evidence():
    client = build_client()

    response = client.get(
        "/research/research_test/claims/clm_test"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["claim"]["claim_id"] == "clm_test"
    assert payload["claim"]["evidence_ids"] == ["evi_test"]

    assert len(payload["evidence"]) == 1
    assert payload["evidence"][0]["evidence_id"] == "evi_test"
    assert payload["evidence"][0]["authority_type"] == (
        "OFFICIAL_DOCUMENTATION"
    )


def test_unknown_authority_is_explicit_when_assessment_is_missing():
    state = build_state()
    state.evidence_assessments = []
    client = build_client(state)

    evidence = client.get(
        "/research/research_test/evidence/evi_test"
    ).json()["evidence"]

    assert evidence["source_type"] == "UNKNOWN"
    assert evidence["authority_type"] == "UNKNOWN"
    assert evidence["authority_level"] == "UNKNOWN"


def test_unknown_evidence_and_claim_return_404():
    client = build_client()

    evidence_response = client.get(
        "/research/research_test/evidence/evi_missing"
    )
    claim_response = client.get(
        "/research/research_test/claims/clm_missing"
    )

    assert evidence_response.status_code == 404
    assert claim_response.status_code == 404
