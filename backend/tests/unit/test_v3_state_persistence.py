from models import (
    AdaptiveResearchState,
    Candidate,
    CandidateDecisionResult,
    DecisionCase,
    DecisionEvaluation,
    DecisionReadiness,
    ReadinessSnapshot,
    ResearchBudget,
    ResearchStoppingDecision,
    IntegrationAssessment,
    ResearchUsage,
    SensitivityResult,
    SummaryState,
    TechnicalContext,
)
from services.research_store import SQLiteResearchStore


def make_v3_state() -> SummaryState:
    candidate = Candidate(
        candidate_id="cand_qdrant",
        name="Qdrant",
    )

    decision = DecisionCase(
        decision_id="dec_test",
        question="Which vector database should we use?",
        candidates=[candidate],
    )

    evaluation = DecisionEvaluation(
        decision_id=decision.decision_id,
        status="complete",
        candidate_results=[
            CandidateDecisionResult(
                candidate_id=candidate.candidate_id,
                status="eligible",
            )
        ],
    )

    readiness = DecisionReadiness(
        decision_id=decision.decision_id,
        overall_score=0.81,
        status="READY",
        criterion_coverage=0.80,
        evidence_quality=0.82,
        applicability=0.79,
        agreement_score=0.90,
        decision_margin=0.75,
        blocking_reasons=[],
        research_gap_ids=[],
    )

    budget = ResearchBudget(
        max_iterations=3,
        max_tasks=9,
        max_searches=12,
    )

    usage = ResearchUsage(
        iterations=2,
        tasks=4,
        searches=6,
    )

    stopping = ResearchStoppingDecision(
        should_continue=False,
        reason="decision_ready",
        readiness_score=0.81,
        readiness_status="READY",
        readiness_improvement=0.07,
        actionable_gap_count=0,
    )

    return SummaryState(
        research_topic="Qdrant vs Milvus",
        decision_case=decision,
        technical_context=TechnicalContext(
            existing_stack=[
                "Python",
                "FastAPI",
            ],
            deployment_environment=[
                "Docker-only",
            ],
            team_capabilities=[
                "small backend team",
            ],
        ),
        integration_assessments=[
            IntegrationAssessment(
                decision_id=decision.decision_id,
                candidate_id="cand_qdrant",
                integration_complexity="LOW",
                migration_complexity="LOW",
                operational_change="LOW",
                infrastructure_change="LOW",
                evidence_ids=[
                    "evi_qdrant_architecture",
                ],
                rationale="Fits the current lightweight stack.",
            )
        ],
        decision_evaluation=evaluation,
        decision_sensitivity=[
            SensitivityResult(
                decision_id=decision.decision_id,
                criterion_id="crit_scale",
                baseline_weight=0.3,
                baseline_winner_id="cand_qdrant",
                score_margin_before=0.6,
                recommendation_changes=True,
                switch_threshold=0.38,
                weight_delta=0.08,
                direction_of_change="increase",
                competing_candidate_id="cand_milvus",
                score_margin_after=-0.04,
            )
        ],
        adaptive_research_state=AdaptiveResearchState(
            decision_id=decision.decision_id,
            iteration_count=2,
            max_iterations=3,
        ),
        decision_readiness=readiness,
        research_budget=budget,
        research_usage=usage,
        readiness_history=[
            ReadinessSnapshot(
                iteration_number=1,
                overall_score=0.60,
                status="TENTATIVE",
            ),
            ReadinessSnapshot(
                iteration_number=2,
                overall_score=0.81,
                status="READY",
            ),
        ],
        stopping_decision=stopping,
    )


def test_sqlite_persists_v3_decision_state(tmp_path):
    db_path = tmp_path / "research.db"

    store = SQLiteResearchStore(db_path)

    original = make_v3_state()

    research_id = store.save(original)

    restored = SQLiteResearchStore(
        db_path
    ).get(research_id)

    assert restored is not None

    assert restored.decision_case is not None
    assert restored.decision_case.decision_id == "dec_test"
    assert restored.decision_case.question == (
        "Which vector database should we use?"
    )

    assert len(
        restored.decision_case.candidates
    ) == 1

    assert (
        restored.decision_case.candidates[0].candidate_id
        == "cand_qdrant"
    )

    assert restored.decision_evaluation is not None

    assert (
        restored.decision_evaluation.candidate_results[0].status
        == "eligible"
    )

    assert restored.decision_readiness is not None
    assert restored.decision_readiness.status == "READY"
    assert restored.decision_readiness.overall_score == 0.81

    assert restored.adaptive_research_state is not None
    assert restored.adaptive_research_state.iteration_count == 2

    assert restored.research_budget is not None
    assert restored.research_budget.max_searches == 12

    assert restored.research_usage is not None
    assert restored.research_usage.searches == 6

    assert len(restored.readiness_history) == 2
    assert restored.readiness_history[-1].status == "READY"

    assert restored.stopping_decision is not None
    assert restored.stopping_decision.should_continue is False
    assert restored.stopping_decision.reason == "decision_ready"


def test_existing_v2_state_loads_with_empty_v3_defaults(tmp_path):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        SummaryState(
            research_topic="ordinary research"
        )
    )

    restored = store.get(research_id)

    assert restored is not None
    assert restored.decision_case is None
    assert restored.technical_context is None
    assert restored.integration_assessments == []
    assert restored.decision_evaluation is None
    assert restored.decision_comparison is None
    assert restored.decision_sensitivity == []
    assert restored.atomic_claims == []
    assert restored.evidence_assessments == []
    assert restored.evidence_signals == []
    assert restored.research_analysis is None
    assert restored.adaptive_research_state is None
    assert restored.decision_readiness is None
    assert restored.readiness_history == []
    assert restored.stopping_decision is None


def test_schema_migrates_existing_research_runs_table(tmp_path):
    import sqlite3

    db_path = tmp_path / "legacy.db"

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE research_runs (
            research_id TEXT PRIMARY KEY,
            research_topic TEXT
        )
        """
    )

    connection.commit()
    connection.close()

    SQLiteResearchStore(db_path)

    connection = sqlite3.connect(db_path)

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(research_runs)"
        ).fetchall()
    }

    connection.close()

    assert "v3_state_json" in columns


def test_sqlite_persists_decision_sensitivity(tmp_path):
    db_path = tmp_path / "sensitivity.db"

    store = SQLiteResearchStore(db_path)

    original = make_v3_state()

    research_id = store.save(original)
    restored = SQLiteResearchStore(db_path).get(research_id)

    assert restored is not None
    assert len(restored.decision_sensitivity) == 1

    sensitivity = restored.decision_sensitivity[0]

    assert isinstance(sensitivity, SensitivityResult)
    assert sensitivity.criterion_id == "crit_scale"
    assert sensitivity.baseline_winner_id == "cand_qdrant"
    assert sensitivity.recommendation_changes is True
    assert sensitivity.switch_threshold == 0.38
    assert sensitivity.competing_candidate_id == "cand_milvus"


def test_sqlite_persists_architecture_context(tmp_path):
    db_path = tmp_path / "architecture_context.db"

    store = SQLiteResearchStore(db_path)

    original = make_v3_state()

    research_id = store.save(original)
    restored = SQLiteResearchStore(db_path).get(research_id)

    assert restored is not None

    assert restored.technical_context is not None
    assert restored.technical_context.existing_stack == [
        "Python",
        "FastAPI",
    ]
    assert restored.technical_context.deployment_environment == [
        "Docker-only",
    ]

    assert len(restored.integration_assessments) == 1

    assessment = restored.integration_assessments[0]

    assert isinstance(
        assessment,
        IntegrationAssessment,
    )
    assert assessment.candidate_id == "cand_qdrant"
    assert assessment.integration_complexity == "LOW"
    assert assessment.evidence_ids == [
        "evi_qdrant_architecture",
    ]


def test_sqlite_persists_recommendation_robustness(tmp_path):
    from models import (
        RecommendationRobustness,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        recommendation_robustness=(
            RecommendationRobustness(
                decision_id="dec_robust",
                baseline_winner_id="cand_a",
                status="MODERATE",
                score_margin=0.8,
                tested_criteria_count=2,
                flip_count=1,
                minimum_flip_delta=0.1,
                minimum_relative_flip_delta=0.1,
                unstable_criterion_ids=[
                    "crit_ops"
                ],
                reasons=[
                    "Weight sensitivity detected."
                ],
            )
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)

    restored = store.get(research_id)

    assert restored is not None
    assert (
        restored.recommendation_robustness
        is not None
    )

    robustness = (
        restored.recommendation_robustness
    )

    assert robustness.status == "MODERATE"
    assert (
        robustness.baseline_winner_id
        == "cand_a"
    )
    assert robustness.flip_count == 1
    assert (
        robustness.unstable_criterion_ids
        == ["crit_ops"]
    )


def test_sqlite_persists_decision_impact_gap_fields(tmp_path):
    from models import (
        ResearchAnalysis,
        ResearchGap,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        research_analysis=ResearchAnalysis(
            decision_id="dec_gap",
            status="gaps_detected",
            research_gaps=[
                ResearchGap(
                    gap_id="gap_impact",
                    candidate_id="cand_a",
                    criterion_id="crit_ops",
                    gap_type="low_coverage",
                    severity=0.7,
                    description="Need evidence",
                    suggested_query=(
                        "A operations Docker-only"
                    ),
                    decision_impact="HIGH",
                    priority=3,
                    impact_reasons=[
                        "Near-flip criterion"
                    ],
                    context_dimensions=[
                        "deployment_environment"
                    ],
                )
            ],
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)
    restored = store.get(research_id)

    assert restored is not None
    assert restored.research_analysis is not None

    gap = (
        restored.research_analysis
        .research_gaps[0]
    )

    assert gap.decision_impact == "HIGH"
    assert gap.priority == 3
    assert gap.impact_reasons == [
        "Near-flip criterion"
    ]
    assert gap.context_dimensions == [
        "deployment_environment"
    ]
