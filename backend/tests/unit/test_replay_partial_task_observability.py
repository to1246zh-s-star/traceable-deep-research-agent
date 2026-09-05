from main import _build_research_replay
from models import (
    Evidence,
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceQuality,
    ExecutionTrace,
    SourceQuality,
    SummaryState,
    TodoItem,
)


def test_replay_exposes_partial_task_failure_type():
    state = SummaryState(
        research_topic="A vs B",
    )

    task = TodoItem(
        id=1,
        title="Research A",
        intent="Collect evidence",
        query="A docs",
        status="partial",
        notices=[
            "summarization_failed:rate_limited",
        ],
    )

    state.todo_items = [task]

    state.execution_traces = [
        ExecutionTrace(
            trace_id="trace_partial",
            task_id=1,
            status="partial",
            error_type="rate_limited",
            error_message="429 rate limit",
        )
    ]

    state.evidence_items = [
        Evidence(
            evidence_id="evi_partial",
            task_id=1,
            trace_id="trace_partial",
            query="A docs",
            backend="tavily",
            source_title="Docs",
            source_url="https://example.com",
        )
    ]
    state.evidence_assessments = [
        EvidenceAssessment(
            evidence_id="evi_partial",
            decision_id="dec_partial",
            source_quality=SourceQuality(
                evidence_id="evi_partial",
                source_type="official_docs",
                confidence=0.95,
                authority_type="OFFICIAL_DOCUMENTATION",
                authority_level="HIGH",
            ),
            evidence_quality=EvidenceQuality(
                evidence_id="evi_partial",
                quality_score=0.9,
                completeness=0.8,
            ),
            applicability=EvidenceApplicability(
                evidence_id="evi_partial",
                decision_id="dec_partial",
                applicability_score=0.9,
            ),
            overall_score=0.9,
        )
    ]

    replay = _build_research_replay(
        "research_partial",
        state,
    )

    assert len(replay["tasks"]) == 1

    task_payload = replay["tasks"][0]

    assert task_payload["status"] == "partial"

    assert task_payload["notices"] == [
        "summarization_failed:rate_limited"
    ]

    assert task_payload["error_types"] == [
        "rate_limited"
    ]

    assert task_payload["evidence_ids"] == [
        "evi_partial"
    ]
    assert task_payload["summary"] is None
    assert task_payload["summary_status"] == "failed"
    assert task_payload["summary_error_type"] == "rate_limited"
    assert task_payload["evidence_count"] == 1
    assert task_payload["sources"] == [
        {
            "source_title": "Docs",
            "source_url": "https://example.com",
            "backend": "tavily",
            "source_rank": None,
            "source_type": "official_docs",
            "authority_type": "OFFICIAL_DOCUMENTATION",
            "authority_level": "HIGH",
        }
    ]


def test_replay_marks_task_without_linked_evidence():
    state = SummaryState(
        research_topic="A vs B",
        todo_items=[
            TodoItem(
                id=1,
                title="Research A",
                intent="Collect evidence",
                query="A docs",
                status="partial",
                notices=["summarization_failed:rate_limited"],
            )
        ],
    )

    replay = _build_research_replay(
        "research_no_evidence",
        state,
    )
    task_payload = replay["tasks"][0]

    assert task_payload["summary"] is None
    assert task_payload["summary_status"] == "failed"
    assert task_payload["summary_error_type"] == "rate_limited"
    assert task_payload["evidence_count"] == 0
    assert task_payload["sources"] == []
