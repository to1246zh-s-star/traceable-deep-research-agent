from models import (
    Candidate,
    DecisionCase,
    DecisionReadiness,
    ResearchAnalysis,
    ResearchGap,
    ResearchStoppingDecision,
    SummaryState,
)
from services.decision_reporting import (
    build_decision_reporting_context,
)


def make_decision():
    return DecisionCase(
        decision_id="dec_report",
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


def make_readiness(
    status,
    *,
    blocking=None,
):
    return DecisionReadiness(
        decision_id="dec_report",
        overall_score=0.61,
        status=status,
        criterion_coverage=0.93,
        evidence_quality=0.70,
        applicability=0.32,
        agreement_score=0.76,
        decision_margin=0.06,
        blocking_reasons=blocking or [],
    )


def make_stopping(
    *,
    reason="budget_exhausted",
    gaps=5,
):
    return ResearchStoppingDecision(
        should_continue=False,
        reason=reason,
        readiness_score=0.61,
        readiness_status="CONFLICTED",
        readiness_improvement=0.01,
        actionable_gap_count=gaps,
        blocking_budget_limits=[],
    )


def test_non_decision_has_no_reporting_context():
    state = SummaryState(
        research_topic="Explain transformers",
    )

    assert (
        build_decision_reporting_context(state)
        == ""
    )


def test_missing_readiness_has_no_reporting_context():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
    )

    assert (
        build_decision_reporting_context(state)
        == ""
    )


def test_ready_allows_definitive_recommendation():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        decision_readiness=make_readiness(
            "READY"
        ),
        stopping_decision=make_stopping(
            reason="decision_ready",
            gaps=0,
        ),
    )

    state.decision_case.recommendation = (
        "Choose candidate A"
    )

    context = build_decision_reporting_context(
        state
    )

    assert (
        "DEFINITIVE_RECOMMENDATION_ALLOWED"
        in context
    )

    assert "Readiness status: READY" in context


def test_conflicted_requires_provisional_language():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        decision_readiness=make_readiness(
            "CONFLICTED",
            blocking=[
                "important evidence conflicts remain unresolved",
            ],
        ),
        stopping_decision=make_stopping(
            reason="budget_exhausted",
            gaps=21,
        ),
    )

    context = build_decision_reporting_context(
        state
    )

    assert "PROVISIONAL_ONLY" in context
    assert (
        "Readiness status: CONFLICTED"
        in context
    )
    assert (
        "Stopping reason: budget_exhausted"
        in context
    )
    assert (
        "Actionable research gaps: 21"
        in context
    )
    assert (
        "important evidence conflicts remain unresolved"
        in context
    )
    assert (
        "does NOT allow a definitive production recommendation"
        in context
    )


def test_tentative_is_not_definitive():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        decision_readiness=make_readiness(
            "TENTATIVE"
        ),
        stopping_decision=make_stopping(),
    )

    context = build_decision_reporting_context(
        state
    )

    assert "PROVISIONAL_ONLY" in context
    assert (
        "DEFINITIVE_RECOMMENDATION_ALLOWED"
        not in context
    )


def test_not_ready_is_not_definitive():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        decision_readiness=make_readiness(
            "NOT_READY"
        ),
        stopping_decision=make_stopping(),
    )

    context = build_decision_reporting_context(
        state
    )

    assert "PROVISIONAL_ONLY" in context


def test_unknown_is_conservative():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        decision_readiness=make_readiness(
            "UNKNOWN"
        ),
        stopping_decision=make_stopping(),
    )

    context = build_decision_reporting_context(
        state
    )

    assert "PROVISIONAL_ONLY" in context


def test_budget_exhaustion_never_implies_ready():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        decision_readiness=make_readiness(
            "CONFLICTED"
        ),
        stopping_decision=make_stopping(
            reason="budget_exhausted",
        ),
    )

    context = build_decision_reporting_context(
        state
    )

    assert "PROVISIONAL_ONLY" in context
    assert (
        "Budget exhaustion means only that "
        "the configured research budget ended"
        in context
    )


def test_falls_back_to_analysis_gap_count_without_stopping():
    gap = ResearchGap(
        gap_id="gap_test",
        candidate_id="cand_a",
        criterion_id="crit_test",
        gap_type="weak_source",
        severity=0.7,
        description="Need stronger evidence",
    )

    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        decision_readiness=make_readiness(
            "CONFLICTED"
        ),
        research_analysis=ResearchAnalysis(
            decision_id="dec_report",
            research_gaps=[gap],
        ),
    )

    context = build_decision_reporting_context(
        state
    )

    assert (
        "Actionable research gaps: 1"
        in context
    )



def _make_ready_reporting_state() -> SummaryState:
    return SummaryState(
        research_topic="Choose A or B",
        decision_case=DecisionCase(
            decision_id="dec_ready_reporting",
            question="Choose A or B",
        ),
        decision_readiness=DecisionReadiness(
            decision_id="dec_ready_reporting",
            overall_score=0.9,
            status="READY",
            criterion_coverage=0.95,
            evidence_quality=0.9,
            applicability=0.9,
            agreement_score=0.9,
            decision_margin=0.2,
            blocking_reasons=[],
        ),
    )



def test_ready_without_structured_recommendation_is_provisional():
    state = _make_ready_reporting_state()

    assert (
        state.decision_case.recommendation
        is None
    )

    context = (
        build_decision_reporting_context(
            state
        )
    )

    assert (
        "Readiness status: READY"
        in context
    )
    assert (
        "Structured recommendation: MISSING"
        in context
    )
    assert (
        "PROVISIONAL_ONLY"
        in context
    )
    assert (
        "DEFINITIVE_RECOMMENDATION_ALLOWED"
        not in context
    )


def test_ready_with_blank_recommendation_is_provisional():
    state = _make_ready_reporting_state()

    state.decision_case.recommendation = "   "

    context = (
        build_decision_reporting_context(
            state
        )
    )

    assert (
        "Structured recommendation: MISSING"
        in context
    )
    assert (
        "PROVISIONAL_ONLY"
        in context
    )


def test_ready_with_structured_recommendation_is_definitive():
    state = _make_ready_reporting_state()

    state.decision_case.recommendation = (
        "Choose candidate A"
    )

    context = (
        build_decision_reporting_context(
            state
        )
    )

    assert (
        "Structured recommendation: PRESENT"
        in context
    )
    assert (
        "DEFINITIVE_RECOMMENDATION_ALLOWED"
        in context
    )
    assert (
        "PROVISIONAL_ONLY"
        not in context
    )
