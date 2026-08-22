from models import (
    Candidate,
    CandidateCriterionScore,
    DecisionCase,
    DecisionCriterion,
    EvidenceAssessment,
    EvidenceApplicability,
    EvidenceQuality,
    EvidenceSignal,
    IntegrationAssessment,
    SourceQuality,
    SummaryState,
    TechnicalContext,
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


def test_decision_pipeline_populates_sensitivity_results():
    decision = DecisionCase(
        decision_id="dec_pipeline_sensitivity",
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
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operations",
                weight=0.7,
            ),
            DecisionCriterion(
                criterion_id="crit_scale",
                name="Scalability",
                weight=0.3,
            ),
        ],
    )

    criterion_scores = [
        CandidateCriterionScore(
            candidate_id="cand_a",
            criterion_id="crit_ops",
            fitness_score=9.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_a",
            criterion_id="crit_scale",
            fitness_score=5.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_b",
            criterion_id="crit_ops",
            fitness_score=6.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_b",
            criterion_id="crit_scale",
            fitness_score=10.0,
        ),
    ]

    state = SummaryState(
        research_topic="Choose A or B",
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=criterion_scores,
    )

    assert state.decision_comparison is not None
    assert state.decision_comparison.status == "complete"

    assert len(state.decision_sensitivity) == 2

    scalability = next(
        result
        for result in state.decision_sensitivity
        if result.criterion_id == "crit_scale"
    )

    assert scalability.recommendation_changes is True
    assert scalability.baseline_winner_id == "cand_a"
    assert scalability.competing_candidate_id == "cand_b"


def test_incomplete_pipeline_clears_sensitivity_results():
    decision = DecisionCase(
        decision_id="dec_pipeline_incomplete_sensitivity",
        question="Choose A or B",
        candidates=[
            Candidate(candidate_id="cand_a", name="A"),
            Candidate(candidate_id="cand_b", name="B"),
        ],
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operations",
                weight=1.0,
            )
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B",
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            )
        ],
    )

    assert state.decision_comparison is not None
    assert state.decision_comparison.status == "incomplete"
    assert state.decision_sensitivity == []


def test_decision_pipeline_stores_architecture_context():
    decision = DecisionCase(
        decision_id="dec_architecture",
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

    context = TechnicalContext(
        existing_stack=[
            "Python",
            "FastAPI",
        ],
        deployment_environment=[
            "Docker-only",
        ],
        team_capabilities=[
            "limited DevOps capacity",
        ],
    )

    assessments = [
        IntegrationAssessment(
            decision_id=decision.decision_id,
            candidate_id="cand_a",
            integration_complexity="LOW",
            migration_complexity="LOW",
            operational_change="LOW",
            infrastructure_change="LOW",
            rationale="Fits the existing deployment model.",
        ),
        IntegrationAssessment(
            decision_id=decision.decision_id,
            candidate_id="cand_b",
            integration_complexity="MEDIUM",
            migration_complexity="MEDIUM",
            operational_change="HIGH",
            infrastructure_change="MEDIUM",
            required_new_dependencies=[
                "additional coordination service",
            ],
            team_skill_gaps=[
                "distributed operations",
            ],
        ),
    ]

    state = SummaryState(
        research_topic="Architecture-aware choice",
    )

    result = run_decision_pipeline(
        state,
        decision,
        technical_context=context,
        integration_assessments=assessments,
    )

    assert result is state
    assert state.technical_context is context

    assert len(state.integration_assessments) == 2

    assert (
        state.integration_assessments[1].candidate_id
        == "cand_b"
    )
    assert (
        state.integration_assessments[1].operational_change
        == "HIGH"
    )


def test_decision_pipeline_preserves_existing_architecture_context():
    original_context = TechnicalContext(
        existing_stack=[
            "Python",
            "FastAPI",
        ],
    )

    original_assessments = [
        IntegrationAssessment(
            decision_id="dec_preserve_context",
            candidate_id="cand_a",
            integration_complexity="LOW",
        )
    ]

    state = SummaryState(
        research_topic="Architecture-aware choice",
        technical_context=original_context,
        integration_assessments=original_assessments,
    )

    decision = DecisionCase(
        decision_id="dec_preserve_context",
        question="Choose A",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            )
        ],
    )

    run_decision_pipeline(
        state,
        decision,
    )

    assert state.technical_context is original_context
    assert state.integration_assessments == original_assessments


