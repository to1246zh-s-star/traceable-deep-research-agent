from copy import deepcopy
from hashlib import sha256

from fastapi.testclient import TestClient

from main import create_app
from models import (
    Candidate,
    Claim,
    DecisionCase,
    DecisionReadiness,
    Evidence,
    ExecutionEvent,
    ExecutionTrace,
    SummaryState,
    TodoItem,
)


def make_state() -> SummaryState:
    state = SummaryState(
        research_topic="Qdrant vs Milvus",
        structured_report="# Technical decision report",
    )

    state.todo_items = [
        TodoItem(
            id=1,
            title="Compare reliability",
            intent="Compare operational reliability",
            query="Qdrant Milvus reliability",
            status="completed",
        )
    ]

    state.execution_traces = [
        ExecutionTrace(
            trace_id="trace_test",
            task_id=1,
            status="completed",
            started_at="2026-08-13T01:00:00+00:00",
            finished_at="2026-08-13T01:01:00+00:00",
        )
    ]

    state.execution_events = [
        ExecutionEvent(
            event_id="evt_test",
            trace_id="trace_test",
            task_id=1,
            event_type="search_completed",
            stage="search",
            timestamp="2026-08-13T01:00:30+00:00",
        )
    ]

    state.evidence_items = [
        Evidence(
            evidence_id="evi_test",
            task_id=1,
            trace_id="trace_test",
            query="Qdrant Milvus reliability",
            backend="web",
            source_title="Benchmark",
            source_url="https://example.com/benchmark",
            snippet="Benchmark result",
            content="Benchmark result",
            source_rank=1,
            created_at="2026-08-13T01:00:40+00:00",
        )
    ]

    state.claims = [
        Claim(
            claim_id="clm_test",
            task_id=1,
            trace_id="trace_test",
            text="Qdrant has simpler operations in this benchmark.",
            evidence_ids=["evi_test"],
            created_at="2026-08-13T01:00:50+00:00",
        )
    ]

    return state


class FakeResearchStore:
    def __init__(self, state):
        self.state = state

    def get(self, research_id):
        if research_id == "research_test":
            return self.state

        return None


def test_replay_endpoint_aggregates_research_artifacts():
    app = create_app()
    app.state.research_store = FakeResearchStore(
        make_state()
    )

    client = TestClient(app)

    response = client.get(
        "/research/research_test/replay"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"] == "research_test"
    assert payload["research_topic"] == "Qdrant vs Milvus"

    assert payload["task_count"] == 1
    assert payload["trace_count"] == 1
    assert payload["claim_count"] == 1
    assert payload["evidence_count"] == 1
    assert payload["report_markdown"] == "# Technical decision report"

    task = payload["tasks"][0]

    assert task["task_id"] == 1
    assert task["trace_ids"] == ["trace_test"]
    assert task["claim_ids"] == ["clm_test"]
    assert task["evidence_ids"] == ["evi_test"]


def test_replay_timeline_is_chronological():
    app = create_app()
    app.state.research_store = FakeResearchStore(
        make_state()
    )

    client = TestClient(app)

    payload = client.get(
        "/research/research_test/replay"
    ).json()

    timestamps = [
        item["timestamp"]
        for item in payload["timeline"]
        if item["timestamp"] is not None
    ]

    assert timestamps == sorted(timestamps)

    event_types = {
        item["event_type"]
        for item in payload["timeline"]
    }

    assert "trace_started" in event_types
    assert "search_completed" in event_types
    assert "evidence_captured" in event_types
    assert "claim_grounded" in event_types
    assert "trace_completed" in event_types


def test_replay_endpoint_returns_404_for_unknown_run():
    app = create_app()
    app.state.research_store = FakeResearchStore(
        make_state()
    )

    client = TestClient(app)

    response = client.get(
        "/research/does-not-exist/replay"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Research run not found"


def test_replay_endpoint_exposes_persisted_adaptive_value_metadata(
    tmp_path,
):
    from models import (
        AdaptiveResearchIteration,
        AdaptiveResearchState,
        Candidate,
        DecisionCase,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_sqlite_replay",
            question="Choose A or B",
            candidates=[
                Candidate(
                    candidate_id="cand_a",
                    name="A",
                ),
                Candidate(
                    candidate_id="cand_b",
                    name="B",
                ),
            ],
        ),
        adaptive_research_state=AdaptiveResearchState(
            decision_id="dec_sqlite_replay",
            iteration_count=1,
            iterations=[
                AdaptiveResearchIteration(
                    decision_id="dec_sqlite_replay",
                    iteration_number=1,
                    status="completed",
                    retrieval_yield_status="LOW_YIELD",
                    evidence_saturation_status="HIGH_SATURATION",
                    information_gain_status="NO_INFORMATION_GAIN",
                    adaptive_research_value_status="LOW_VALUE",
                    research_value_summary=(
                        "This research iteration added limited "
                        "decision-relevant value."
                    ),
                    research_value_explanation=[
                        "retrieval yield: low_yield",
                        (
                            "evidence saturation: "
                            "high_saturation"
                        ),
                        (
                            "decision information gain: "
                            "no_information_gain"
                        ),
                        (
                            "adaptive research value: "
                            "low_value"
                        ),
                    ],
                    research_value_observations=[
                        "6 new evidence item(s)",
                    ],
                    stopping_explanation=(
                        "Adaptive research stopped because "
                        "marginal research value showed "
                        "diminishing returns."
                    ),
                )
            ],
        ),
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        state
    )

    app = create_app()
    app.state.research_store = store

    client = TestClient(app)

    response = client.get(
        f"/research/{research_id}/replay"
    )

    assert response.status_code == 200

    payload = response.json()

    item = payload[
        "decision"
    ][
        "adaptive_research_state"
    ][
        "iterations"
    ][0]

    assert (
        item["retrieval_yield_status"]
        == "LOW_YIELD"
    )

    assert (
        item["evidence_saturation_status"]
        == "HIGH_SATURATION"
    )

    assert (
        item["information_gain_status"]
        == "NO_INFORMATION_GAIN"
    )

    assert (
        item["adaptive_research_value_status"]
        == "LOW_VALUE"
    )

    assert (
        item["research_value_summary"]
        == (
            "This research iteration added limited "
            "decision-relevant value."
        )
    )

    assert (
        "adaptive research value: low_value"
        in item["research_value_explanation"]
    )

    assert (
        "6 new evidence item(s)"
        in item["research_value_observations"]
    )

    assert (
        "diminishing returns"
        in item["stopping_explanation"]
    )


def test_replay_endpoint_only_reads_stored_state():
    state = make_state()

    class ReadOnlyResearchStore:
        def __init__(self):
            self.get_calls = 0

        def get(self, research_id):
            self.get_calls += 1

            if research_id == "research_read_only":
                return state

            return None

    store = ReadOnlyResearchStore()

    app = create_app()
    app.state.research_store = store

    client = TestClient(app)

    response = client.get(
        "/research/research_read_only/replay"
    )

    assert response.status_code == 200
    assert store.get_calls == 1


def test_replay_projects_legacy_report_without_mutating_audit_state():
    legacy_report = """# Legacy report

Recompute affected modules: decision_comparison.
counterfactual dependency path
No evidence signals exist for A x reliability.
"""
    state = SummaryState(
        research_topic="Choose A or B",
        structured_report=legacy_report,
        decision_case=DecisionCase(
            decision_id="dec_legacy",
            question="Choose A or B",
            candidates=[
                Candidate(candidate_id="cand_a", name="A"),
                Candidate(candidate_id="cand_b", name="B"),
            ],
        ),
        decision_readiness=DecisionReadiness(
            decision_id="dec_legacy",
            overall_score=0.0,
            status="INSUFFICIENT_EVIDENCE",
            criterion_coverage=0.0,
            evidence_quality=0.0,
            applicability=0.0,
            agreement_score=0.0,
            decision_margin=0.0,
            blocking_reasons=[
                "candidate eligibility remains unresolved",
            ],
        ),
    )
    before = deepcopy(state)
    stored_report_hash = sha256(
        state.structured_report.encode("utf-8")
    ).hexdigest()

    app = create_app()
    app.state.research_store = FakeResearchStore(state)
    response = TestClient(app).get(
        "/research/research_test/replay"
    )

    assert response.status_code == 200
    report = response.json()["report_markdown"]
    for phrase in (
        "Recompute affected modules",
        "counterfactual dependency path",
        "No evidence signals exist",
        "candidate eligibility remains unresolved",
    ):
        assert phrase not in report
    assert "推荐：暂不形成确定推荐" in report
    assert state == before
    assert sha256(
        state.structured_report.encode("utf-8")
    ).hexdigest() == stored_report_hash
