from types import SimpleNamespace
from fastapi.testclient import TestClient

import main
from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    ReevaluationAssessment,
    ReevaluationPlan,
    ReevaluationPreparation,
    ReevaluationReactivationDecision,
    ResearchAnalysis,
    ResearchGap,
    ResearchStoppingDecision,
    SummaryState,
)
from services.research_store import (
    InMemoryResearchStore,
)


def build_decision():
    return DecisionCase(
        decision_id="dec_test",
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
    )


def build_state():
    return SummaryState(
        research_topic="A vs B",
        decision_case=build_decision(),
        research_analysis=ResearchAnalysis(
            decision_id="dec_test",
            status="complete",
        ),
        adaptive_research_state=(
            AdaptiveResearchState(
                decision_id="dec_test",
                status="stopped",
            )
        ),
        stopping_decision=(
            ResearchStoppingDecision(
                should_continue=False,
                reason=(
                    "insufficient_marginal_improvement"
                ),
                readiness_score=0.6,
                readiness_status="CONFLICTED",
            )
        ),
        running_summary="OLD REPORT",
        structured_report="OLD REPORT",
    )


def make_app():
    app = main.create_app()

    # Avoid touching the configured SQLite DB and make object identity
    # assertions deterministic.
    app.state.research_store = (
        InMemoryResearchStore()
    )

    return app


def eligible_preparation():
    gap = ResearchGap(
        gap_id="gap_reeval",
        candidate_id="",
        criterion_id="",
        gap_type="reevaluation",
        severity=1.0,
        description="Recheck changed context",
        suggested_query="changed context",
        priority=3,
    )

    return ReevaluationPreparation(
        decision_id="dec_test",
        assessment=ReevaluationAssessment(
            decision_id="dec_test",
            status="REQUIRED",
        ),
        plan=ReevaluationPlan(
            decision_id="dec_test",
            status="REQUIRED",
            research_queries=[
                "changed context",
            ],
        ),
        reevaluation_gaps=[
            gap,
        ],
        merged_analysis=ResearchAnalysis(
            decision_id="dec_test",
            research_gaps=[
                gap,
            ],
            status="gaps_detected",
        ),
        reactivation=(
            ReevaluationReactivationDecision(
                decision_id="dec_test",
                status="ELIGIBLE",
                eligible=True,
                actionable_gap_ids=[
                    "gap_reeval",
                ],
            )
        ),
    )


def test_reevaluate_returns_404_for_unknown_research():
    app = make_app()
    client = TestClient(app)

    response = client.post(
        "/research/research_missing/reevaluate",
        json={},
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Research run not found"
    )


def test_reevaluate_rejects_run_without_decision():
    app = make_app()
    client = TestClient(app)

    research_id = (
        app.state.research_store.save(
            SummaryState(
                research_topic="informational",
            )
        )
    )

    response = client.post(
        f"/research/{research_id}/reevaluate",
        json={},
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Research run has no technical decision"
    )


def test_reevaluate_rejects_run_without_analysis():
    app = make_app()
    client = TestClient(app)

    state = SummaryState(
        research_topic="A vs B",
        decision_case=build_decision(),
        adaptive_research_state=(
            AdaptiveResearchState(
                decision_id="dec_test",
                status="stopped",
            )
        ),
    )

    research_id = (
        app.state.research_store.save(
            state
        )
    )

    response = client.post(
        f"/research/{research_id}/reevaluate",
        json={},
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Research run has no research analysis"
    )


def test_reevaluate_rejects_run_without_adaptive_state():
    app = make_app()
    client = TestClient(app)

    state = SummaryState(
        research_topic="A vs B",
        decision_case=build_decision(),
        research_analysis=ResearchAnalysis(
            decision_id="dec_test",
        ),
    )

    research_id = (
        app.state.research_store.save(
            state
        )
    )

    response = client.post(
        f"/research/{research_id}/reevaluate",
        json={},
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == (
            "Research run has no "
            "adaptive research state"
        )
    )


def test_unknown_reevaluation_does_not_create_version():
    app = make_app()
    client = TestClient(app)

    original = build_state()

    source_id = (
        app.state.research_store.save(
            original
        )
    )

    before = (
        app.state.research_store.list()
    )

    # No structured observation + no triggers:
    # deterministic assessor must remain UNKNOWN.
    response = client.post(
        f"/research/{source_id}/reevaluate",
        json={
            "observed_facts": [
                "Something may have changed"
            ],
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["source_research_id"] == source_id
    assert payload["research_id"] is None
    assert payload["executed"] is False
    assert payload["eligible"] is False
    assert payload["status"] == "UNKNOWN"

    after = (
        app.state.research_store.list()
    )

    assert len(after) == len(before)
    assert len(after) == 1


def test_unknown_reevaluation_preserves_historical_state():
    app = make_app()
    client = TestClient(app)

    original = build_state()

    source_id = (
        app.state.research_store.save(
            original
        )
    )

    old_analysis = original.research_analysis
    old_status = (
        original.adaptive_research_state.status
    )
    old_report = original.structured_report

    response = client.post(
        f"/research/{source_id}/reevaluate",
        json={},
    )

    assert response.status_code == 200

    restored = (
        app.state.research_store.get(
            source_id
        )
    )

    assert restored is original

    assert (
        restored.research_analysis
        is old_analysis
    )

    assert (
        restored.adaptive_research_state.status
        == old_status
    )

    assert (
        restored.structured_report
        == old_report
    )


def test_eligible_reevaluation_creates_new_version(
    monkeypatch,
):
    app = make_app()
    client = TestClient(app)

    original = build_state()

    source_id = (
        app.state.research_store.save(
            original
        )
    )

    preparation = (
        eligible_preparation()
    )

    monkeypatch.setattr(
        main,
        "prepare_reevaluation",
        lambda *args, **kwargs: preparation,
    )

    monkeypatch.setattr(
        app.state.llm_preflight_guard,
        "check",
        lambda probe: SimpleNamespace(
            available=True,
            code="ok",
            reason="ok",
        ),
    )

    class FakeReporting:
        def generate_report(
            self,
            state,
        ):
            return "NEW REPORT"

    class FakeAgent:
        def __init__(
            self,
            config=None,
        ):
            self.config = config
            self.reporting = FakeReporting()

        def execute_prepared_reevaluation(
            self,
            state,
            preparation,
        ):
            state.research_analysis = (
                preparation.merged_analysis
            )

            state.adaptive_research_state.status = (
                "active"
            )

            return state

    monkeypatch.setattr(
        main,
        "DeepResearchAgent",
        FakeAgent,
    )

    response = client.post(
        f"/research/{source_id}/reevaluate",
        json={
            "observed_trigger_ids": [
                "trg_changed",
            ],
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["source_research_id"] == source_id
    assert payload["executed"] is True
    assert payload["eligible"] is True
    assert payload["status"] == "REQUIRED"

    new_id = payload["research_id"]

    assert new_id is not None
    assert new_id != source_id

    assert len(
        app.state.research_store.list()
    ) == 2


def test_eligible_reevaluation_does_not_mutate_old_version(
    monkeypatch,
):
    app = make_app()
    client = TestClient(app)

    original = build_state()

    old_analysis = (
        original.research_analysis
    )

    old_adaptive_status = (
        original.adaptive_research_state.status
    )

    source_id = (
        app.state.research_store.save(
            original
        )
    )

    preparation = (
        eligible_preparation()
    )

    monkeypatch.setattr(
        main,
        "prepare_reevaluation",
        lambda *args, **kwargs: preparation,
    )

    monkeypatch.setattr(
        app.state.llm_preflight_guard,
        "check",
        lambda probe: SimpleNamespace(
            available=True,
            code="ok",
            reason="ok",
        ),
    )

    class FakeReporting:
        def generate_report(
            self,
            state,
        ):
            return "NEW REPORT"

    class FakeAgent:
        def __init__(
            self,
            config=None,
        ):
            self.reporting = FakeReporting()

        def execute_prepared_reevaluation(
            self,
            state,
            preparation,
        ):
            # Deliberately mutate the WORKING COPY heavily.
            state.research_analysis = (
                preparation.merged_analysis
            )

            state.adaptive_research_state.status = (
                "active"
            )

            state.running_summary = (
                "WORKING COPY MUTATED"
            )

            return state

    monkeypatch.setattr(
        main,
        "DeepResearchAgent",
        FakeAgent,
    )

    response = client.post(
        f"/research/{source_id}/reevaluate",
        json={},
    )

    assert response.status_code == 200

    new_id = (
        response.json()["research_id"]
    )

    old_state = (
        app.state.research_store.get(
            source_id
        )
    )

    new_state = (
        app.state.research_store.get(
            new_id
        )
    )

    assert old_state is original

    assert (
        old_state.research_analysis
        is old_analysis
    )

    assert (
        old_state.adaptive_research_state.status
        == old_adaptive_status
    )

    assert (
        old_state.structured_report
        == "OLD REPORT"
    )

    assert (
        old_state.running_summary
        == "OLD REPORT"
    )

    assert new_state is not old_state

    assert (
        new_state.research_analysis
        is not old_analysis
    )

    assert (
        new_state.structured_report
        == "NEW REPORT"
    )

    assert (
        new_state.running_summary
        == "NEW REPORT"
    )


def test_new_version_clears_old_report_note_references(
    monkeypatch,
):
    app = make_app()
    client = TestClient(app)

    original = build_state()

    original.report_note_id = (
        "old_note"
    )

    original.report_note_path = (
        "/old/report.md"
    )

    source_id = (
        app.state.research_store.save(
            original
        )
    )

    monkeypatch.setattr(
        main,
        "prepare_reevaluation",
        lambda *args, **kwargs: (
            eligible_preparation()
        ),
    )

    monkeypatch.setattr(
        app.state.llm_preflight_guard,
        "check",
        lambda probe: SimpleNamespace(
            available=True,
            code="ok",
            reason="ok",
        ),
    )

    class FakeReporting:
        def generate_report(
            self,
            state,
        ):
            return "NEW REPORT"

    class FakeAgent:
        def __init__(
            self,
            config=None,
        ):
            self.reporting = FakeReporting()

        def execute_prepared_reevaluation(
            self,
            state,
            preparation,
        ):
            return state

    monkeypatch.setattr(
        main,
        "DeepResearchAgent",
        FakeAgent,
    )

    response = client.post(
        f"/research/{source_id}/reevaluate",
        json={},
    )

    assert response.status_code == 200

    new_id = (
        response.json()["research_id"]
    )

    old_state = (
        app.state.research_store.get(
            source_id
        )
    )

    new_state = (
        app.state.research_store.get(
            new_id
        )
    )

    assert (
        old_state.report_note_id
        == "old_note"
    )

    assert (
        old_state.report_note_path
        == "/old/report.md"
    )

    assert (
        new_state.report_note_id
        is None
    )

    assert (
        new_state.report_note_path
        is None
    )
