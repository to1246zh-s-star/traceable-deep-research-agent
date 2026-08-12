from models import (
    Candidate,
    CandidateCriterionScore,
    DecisionCase,
    DecisionCriterion,
    EvidenceAssessment,
    EvidenceApplicability,
    EvidenceQuality,
    EvidenceSignal,
    SourceQuality,
    SummaryState,
)
from services.decision_pipeline import run_decision_pipeline


def test_decision_pipeline_populates_v3_state():
    decision = DecisionCase(
        decision_id="dec_pipeline",
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

    criterion_scores = [
        CandidateCriterionScore(
            candidate_id="cand_qdrant",
            criterion_id="crit_ops",
            fitness_score=8.0,
            rationale="Simpler operational footprint",
        ),
        CandidateCriterionScore(
            candidate_id="cand_milvus",
            criterion_id="crit_ops",
            fitness_score=6.0,
            rationale="More operational components",
        ),
    ]

    signals = [
        EvidenceSignal(
            evidence_id="evi_qdrant",
            candidate_id="cand_qdrant",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.9,
            source_confidence=0.9,
            applicability=0.9,
        ),
        EvidenceSignal(
            evidence_id="evi_milvus",
            candidate_id="cand_milvus",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.8,
            source_confidence=0.8,
            applicability=0.8,
        ),
    ]

    assessments = [
        EvidenceAssessment(
            evidence_id="evi_qdrant",
            decision_id="dec_pipeline",
            source_quality=SourceQuality(
                evidence_id="evi_qdrant",
                source_type="official_docs",
                confidence=0.95,
            ),
            evidence_quality=EvidenceQuality(
                evidence_id="evi_qdrant",
                quality_score=0.9,
                completeness=0.9,
            ),
            applicability=EvidenceApplicability(
                evidence_id="evi_qdrant",
                decision_id="dec_pipeline",
                applicability_score=0.9,
            ),
            overall_score=0.7695,
        )
    ]

    state = SummaryState(
        research_topic="Qdrant vs Milvus"
    )

    result = run_decision_pipeline(
        state,
        decision,
        criterion_scores=criterion_scores,
        evidence_signals=signals,
        evidence_assessments=assessments,
    )

    assert result is state

    assert state.decision_case is decision
    assert state.decision_evaluation is not None
    assert state.decision_comparison is not None
    assert state.research_analysis is not None
    assert state.decision_readiness is not None
    assert state.stopping_decision is not None

    assert state.decision_comparison.ranked_candidate_ids[0] == (
        "cand_qdrant"
    )

    assert len(state.readiness_history) == 1

    assert state.readiness_history[0].overall_score == (
        state.decision_readiness.overall_score
    )


def test_decision_pipeline_accumulates_readiness_history():
    decision = DecisionCase(
        decision_id="dec_history",
        question="Choose a database",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            )
        ],
    )

    state = SummaryState(
        research_topic="Database choice"
    )

    run_decision_pipeline(
        state,
        decision,
    )

    run_decision_pipeline(
        state,
        decision,
    )

    assert len(state.readiness_history) == 2
    assert state.readiness_history[0].iteration_number == 1
    assert state.readiness_history[1].iteration_number == 2


def test_decision_pipeline_auto_builds_evidence_inputs():
    from models import Evidence

    state = SummaryState(
        research_topic="Qdrant operational simplicity",
        evidence_items=[
            Evidence(
                evidence_id="evi_auto",
                task_id=1,
                trace_id="trace_auto",
                query="Qdrant operational simplicity",
                backend="web",
                source_title="Qdrant Documentation",
                source_url="https://qdrant.tech/documentation/",
                snippet=(
                    "Qdrant operational simplicity and deployment "
                    "are described in the documentation."
                ),
                content=None,
                source_rank=1,
            )
        ],
    )

    decision = DecisionCase(
        decision_id="dec_auto_inputs",
        question="Which vector database should we choose?",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            )
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

    result = run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_qdrant",
                criterion_id="crit_ops",
                fitness_score=8.0,
                rationale="Simple operations",
            )
        ],
    )

    assert result is state

    assert len(state.evidence_assessments) == 1
    assert state.evidence_assessments[0].evidence_id == "evi_auto"

    assert len(state.evidence_signals) == 1

    signal = state.evidence_signals[0]
    assert signal.evidence_id == "evi_auto"
    assert signal.candidate_id == "cand_qdrant"
    assert signal.criterion_id == "crit_ops"

    assert state.research_analysis is not None
    assert state.decision_readiness is not None
