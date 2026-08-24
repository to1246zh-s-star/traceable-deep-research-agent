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




def test_decision_pipeline_stores_recommendation_robustness():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_robust_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    scores = [
        CandidateCriterionScore(
            candidate_id="cand_a",
            criterion_id="crit_ops",
            fitness_score=8.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_b",
            criterion_id="crit_ops",
            fitness_score=6.0,
        ),
    ]

    result = run_decision_pipeline(
        state,
        decision,
        constraint_results={},
        criterion_scores=scores,
        evidence_signals=[],
        evidence_assessments=[],
    )

    assert result is state
    assert (
        state.recommendation_robustness
        is not None
    )

    robustness = (
        state.recommendation_robustness
    )

    assert (
        robustness.baseline_winner_id
        == "cand_a"
    )

    assert robustness.score_margin == 2.0

    assert robustness.status in {
        "ROBUST",
        "MODERATE",
        "FRAGILE",
    }



def test_pipeline_enriches_gap_decision_impact():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
        TechnicalContext,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_gap_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
        technical_context=TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
    )

    assert state.research_analysis is not None

    gaps = state.research_analysis.research_gaps

    assert gaps

    assert all(
        gap.decision_impact
        in {
            "HIGH",
            "MEDIUM",
            "LOW",
            "UNKNOWN",
        }
        for gap in gaps
    )

    winner_gaps = [
        gap
        for gap in gaps
        if gap.candidate_id == "cand_a"
    ]

    assert winner_gaps

    assert all(
        gap.priority >= 2
        for gap in winner_gaps
    )

    assert all(
        "Docker-only"
        in (gap.suggested_query or "")
        for gap in gaps
    )


def test_pipeline_attaches_expected_decision_impact():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_expected_impact",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
    )

    gaps = state.research_analysis.research_gaps

    assert gaps

    for item in gaps:
        impact = item.expected_decision_impact

        assert impact is not None
        assert impact.gap_id == item.gap_id

        assert impact.overall_impact in {
            "HIGH",
            "MEDIUM",
            "LOW",
            "UNKNOWN",
        }


def test_pipeline_stores_decision_assumptions():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
        TechnicalContext,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_assumption_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
        technical_context=TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
    )

    assert state.decision_assumptions

    assert any(
        item.assumption_type == "CONTEXT"
        for item in state.decision_assumptions
    )

    assert any(
        item.assumption_type == "PRIORITY"
        for item in state.decision_assumptions
    )


def test_pipeline_stores_decision_assumptions():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
        TechnicalContext,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_assumption_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
        technical_context=TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
    )

    assert state.decision_assumptions

    assert any(
        item.assumption_type == "CONTEXT"
        for item in state.decision_assumptions
    )

    assert any(
        item.assumption_type == "PRIORITY"
        for item in state.decision_assumptions
    )


def test_pipeline_stores_decision_assumptions():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
        TechnicalContext,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_assumption_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
        technical_context=TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
    )

    assert state.decision_assumptions

    assert any(
        item.assumption_type == "CONTEXT"
        for item in state.decision_assumptions
    )

    assert any(
        item.assumption_type == "PRIORITY"
        for item in state.decision_assumptions
    )


def test_pipeline_stores_decision_counterfactuals():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
        TechnicalContext,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_cf_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
        technical_context=TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
    )

    assert state.decision_assumptions
    assert state.decision_counterfactuals

    assumption_ids = {
        item.assumption_id
        for item in state.decision_assumptions
    }

    assert all(
        item.assumption_id in assumption_ids
        for item in state.decision_counterfactuals
    )

    assert all(
        item.recommendation_instability
        in {
            "HIGH",
            "MEDIUM",
            "LOW",
            "UNKNOWN",
        }
        for item in state.decision_counterfactuals
    )


def test_pipeline_stores_decision_scenarios():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
        TechnicalContext,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_scenario_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
        technical_context=TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ],
            team_capabilities=[
                "small DevOps team"
            ],
        ),
    )

    assert state.decision_counterfactuals
    assert state.decision_scenarios

    counterfactual_ids = {
        item.counterfactual_id
        for item in state.decision_counterfactuals
    }

    assert all(
        set(item.counterfactual_ids)
        <= counterfactual_ids
        for item in state.decision_scenarios
    )

    assert all(
        item.scenario_instability
        in {
            "HIGH",
            "MEDIUM",
            "LOW",
            "UNKNOWN",
        }
        for item in state.decision_scenarios
    )


def test_pipeline_stores_reevaluation_triggers():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
        TechnicalContext,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_trigger_pipeline",
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
                weight=1.0,
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_ops",
                fitness_score=6.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
        technical_context=TechnicalContext(
            deployment_environment=[
                "Docker-only"
            ]
        ),
    )

    assert state.decision_assumptions
    assert state.decision_reevaluation_triggers

    assert all(
        item.trigger_impact
        in {
            "HIGH",
            "MEDIUM",
            "LOW",
            "UNKNOWN",
        }
        for item
        in state.decision_reevaluation_triggers
    )

    assert any(
        item.trigger_type
        == "TECHNICAL_CONTEXT_CHANGE"
        for item
        in state.decision_reevaluation_triggers
    )

    assert any(
        item.trigger_type
        == "CRITERION_PRIORITY_CHANGE"
        for item
        in state.decision_reevaluation_triggers
    )


def test_pipeline_attaches_search_strategy_to_research_gaps():
    from models import (
        Candidate,
        CandidateCriterionScore,
        DecisionCase,
        DecisionCriterion,
        SummaryState,
    )
    from services.decision_pipeline import (
        run_decision_pipeline,
    )

    decision = DecisionCase(
        decision_id="dec_search_strategy",
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
                criterion_id="crit_scale",
                name="Scalability",
                weight=1.0,
            )
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_scale",
                fitness_score=8.0,
            ),
            CandidateCriterionScore(
                candidate_id="cand_b",
                criterion_id="crit_scale",
                fitness_score=7.0,
            ),
        ],
        evidence_signals=[],
        evidence_assessments=[],
    )

    assert (
        state.research_analysis
        is not None
    )

    gaps = (
        state
        .research_analysis
        .research_gaps
    )

    assert gaps

    assert all(
        gap.search_strategy
        for gap in gaps
    )

    scale_gaps = [
        gap
        for gap in gaps
        if gap.criterion_id
        == "crit_scale"
    ]

    assert scale_gaps

    assert all(
        gap.search_strategy
        == "PERFORMANCE_SCALE"
        for gap in scale_gaps
    )

    assert all(
        "benchmark"
        in gap.preferred_source_types
        for gap in scale_gaps
    )
