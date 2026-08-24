from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    Evidence,
    SummaryState,
)
from services.decision_input_builder import (
    attach_evidence_assessments,
    build_evidence_assessments,
)


def make_state() -> SummaryState:
    return SummaryState(
        research_topic="Qdrant vs Milvus",
        evidence_items=[
            Evidence(
                evidence_id="evi_official",
                task_id=1,
                trace_id="trace_1",
                query="Qdrant operational simplicity",
                backend="web",
                source_title="Qdrant Documentation",
                source_url="https://qdrant.tech/documentation/",
                snippet=(
                    "Qdrant documentation describes deployment "
                    "and operational configuration."
                ),
                content=(
                    "Qdrant supports deployment and operational "
                    "configuration workflows."
                ),
                source_rank=1,
            ),
            Evidence(
                evidence_id="evi_blog",
                task_id=1,
                trace_id="trace_1",
                query="Qdrant operational simplicity",
                backend="web",
                source_title="Vector Database Comparison",
                source_url="https://example.com/vector-db-comparison",
                snippet="A comparison of vector database operations.",
                content="Qdrant and Milvus have different operational tradeoffs.",
                source_rank=2,
            ),
        ],
    )


def make_decision() -> DecisionCase:
    return DecisionCase(
        decision_id="dec_builder",
        question="Which vector database should we choose?",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            ),
            Candidate(
                candidate_id="cand_milvus",
                name="Milvus",
            ),
        ],
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operational simplicity",
                weight=1.0,
                source="user",
            )
        ],
    )


def test_build_evidence_assessments_for_all_research_evidence():
    state = make_state()
    decision = make_decision()

    assessments = build_evidence_assessments(
        state,
        decision,
    )

    assert len(assessments) == 2

    assert {
        assessment.evidence_id
        for assessment in assessments
    } == {
        "evi_official",
        "evi_blog",
    }

    for assessment in assessments:
        assert assessment.decision_id == "dec_builder"
        assert 0.0 <= assessment.overall_score <= 1.0


def test_attach_evidence_assessments_updates_state():
    state = make_state()
    decision = make_decision()

    result = attach_evidence_assessments(
        state,
        decision,
    )

    assert result is state
    assert len(state.evidence_assessments) == 2
    assert state.evidence_assessments[0].decision_id == (
        "dec_builder"
    )


def test_build_evidence_signals_matches_candidate_and_criterion():
    from services.decision_input_builder import (
        build_evidence_signals,
    )

    state = make_state()
    decision = make_decision()

    attach_evidence_assessments(
        state,
        decision,
    )

    signals = build_evidence_signals(
        state,
        decision,
    )

    qdrant_signals = [
        signal
        for signal in signals
        if signal.candidate_id == "cand_qdrant"
    ]

    assert qdrant_signals

    signal = qdrant_signals[0]

    assert signal.evidence_id == "evi_official"
    assert signal.criterion_id == "crit_ops"
    assert signal.direction == "neutral"
    assert 0.0 <= signal.strength <= 1.0
    assert 0.0 <= signal.source_confidence <= 1.0
    assert 0.0 <= signal.applicability <= 1.0


def test_build_evidence_signals_skips_unmatched_candidate():
    from services.decision_input_builder import (
        build_evidence_signals,
    )

    state = SummaryState(
        research_topic="Vector database research",
        evidence_items=[
            Evidence(
                evidence_id="evi_unrelated",
                task_id=1,
                trace_id="trace_1",
                query="database operations",
                backend="web",
                source_title="General Database Guide",
                snippet=(
                    "Operational simplicity can reduce "
                    "maintenance overhead."
                ),
                content=None,
                source_rank=1,
            )
        ],
    )

    decision = make_decision()

    signals = build_evidence_signals(
        state,
        decision,
    )

    assert signals == []


def test_attach_evidence_signals_updates_state():
    from services.decision_input_builder import (
        attach_evidence_signals,
    )

    state = make_state()
    decision = make_decision()

    attach_evidence_assessments(
        state,
        decision,
    )

    result = attach_evidence_signals(
        state,
        decision,
    )

    assert result is state
    assert state.evidence_signals


def test_source_authority_flows_into_evidence_signal_confidence():
    state = make_state()
    decision = make_decision()

    assessments = build_evidence_assessments(
        state,
        decision,
    )

    state.evidence_assessments = (
        assessments
    )

    official = next(
        item
        for item in assessments
        if item.evidence_id
        == "evi_official"
    )

    assert (
        official
        .source_quality
        .authority_type
        == "OFFICIAL_DOCUMENTATION"
    )

    from services.decision_input_builder import (
        build_evidence_signals,
    )

    signals = build_evidence_signals(
        state,
        decision,
    )

    signal = next(
        item
        for item in signals
        if item.evidence_id
        == "evi_official"
    )

    assert (
        signal.source_confidence
        == official.source_quality.confidence
    )
