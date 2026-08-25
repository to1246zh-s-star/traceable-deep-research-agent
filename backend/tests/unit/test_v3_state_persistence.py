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


def test_sqlite_persists_expected_decision_impact(tmp_path):
    from models import (
        ExpectedDecisionImpact,
        ResearchAnalysis,
        ResearchGap,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        research_analysis=ResearchAnalysis(
            decision_id="dec_impact",
            research_gaps=[
                ResearchGap(
                    gap_id="gap_expected",
                    candidate_id="cand_a",
                    criterion_id="crit_ops",
                    gap_type="low_coverage",
                    severity=0.8,
                    description="Need evidence",
                    expected_decision_impact=(
                        ExpectedDecisionImpact(
                            decision_id="dec_impact",
                            gap_id="gap_expected",
                            overall_impact="HIGH",
                            ranking_impact="HIGH",
                            constraint_impact="LOW",
                            architecture_impact="MEDIUM",
                            conflict_resolution_impact="LOW",
                            readiness_impact="HIGH",
                            robustness_impact="MEDIUM",
                            drivers=[
                                "Ranking sensitive"
                            ],
                        )
                    ),
                )
            ],
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)
    restored = store.get(research_id)

    impact = (
        restored
        .research_analysis
        .research_gaps[0]
        .expected_decision_impact
    )

    assert impact is not None
    assert impact.overall_impact == "HIGH"
    assert impact.ranking_impact == "HIGH"
    assert impact.readiness_impact == "HIGH"
    assert impact.drivers == [
        "Ranking sensitive"
    ]


def test_sqlite_persists_decision_assumptions(tmp_path):
    from models import (
        DecisionAssumption,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        decision_assumptions=[
            DecisionAssumption(
                assumption_id="asm_test",
                decision_id="dec_test",
                text=(
                    "Deployment environment remains "
                    "Docker-only."
                ),
                assumption_type="CONTEXT",
                source_type="technical_context",
                source_field=(
                    "deployment_environment"
                ),
                source_value="Docker-only",
                affected_candidate_ids=[
                    "cand_a",
                    "cand_b",
                ],
                change_sensitivity="MEDIUM",
                decision_impact="HIGH",
                rationale="Context-dependent fit.",
            )
        ]
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)
    restored = store.get(research_id)

    assert restored is not None
    assert len(
        restored.decision_assumptions
    ) == 1

    item = restored.decision_assumptions[0]

    assert item.assumption_id == "asm_test"
    assert item.decision_impact == "HIGH"
    assert item.source_value == "Docker-only"


def test_sqlite_persists_decision_counterfactuals(tmp_path):
    from models import (
        DecisionCounterfactual,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        decision_counterfactuals=[
            DecisionCounterfactual(
                counterfactual_id="cf_test",
                decision_id="dec_test",
                assumption_id="asm_test",
                statement=(
                    "If Docker-only no longer holds, "
                    "re-evaluate the decision."
                ),
                assumption_type="CONTEXT",
                source_field=(
                    "deployment_environment"
                ),
                source_value="Docker-only",
                affected_candidate_ids=[
                    "cand_a",
                    "cand_b",
                ],
                affected_dimensions=[
                    "architecture_fit",
                    "integration",
                ],
                recommendation_instability="HIGH",
                reevaluation_required=True,
                rationale=[
                    "Architecture depends on context."
                ],
            )
        ]
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)
    restored = store.get(research_id)

    assert restored is not None

    assert len(
        restored.decision_counterfactuals
    ) == 1

    item = (
        restored
        .decision_counterfactuals[0]
    )

    assert item.counterfactual_id == "cf_test"
    assert item.assumption_id == "asm_test"

    assert (
        item.recommendation_instability
        == "HIGH"
    )

    assert item.reevaluation_required is True

    assert item.affected_dimensions == [
        "architecture_fit",
        "integration",
    ]


def test_sqlite_persists_decision_scenarios(tmp_path):
    from models import (
        DecisionScenario,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        decision_scenarios=[
            DecisionScenario(
                scenario_id="scn_test",
                decision_id="dec_test",
                scenario_type="ARCHITECTURE",
                title="Architecture context changes",
                counterfactual_ids=[
                    "cf_1",
                    "cf_2",
                ],
                assumption_ids=[
                    "asm_1",
                    "asm_2",
                ],
                affected_candidate_ids=[
                    "cand_a",
                    "cand_b",
                ],
                affected_dimensions=[
                    "architecture_fit",
                    "integration",
                    "operations",
                ],
                scenario_instability="HIGH",
                reevaluation_required=True,
                rationale=[
                    "Architecture assumptions changed."
                ],
            )
        ]
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)
    restored = store.get(research_id)

    assert restored is not None

    assert len(
        restored.decision_scenarios
    ) == 1

    item = restored.decision_scenarios[0]

    assert item.scenario_id == "scn_test"
    assert item.scenario_type == "ARCHITECTURE"

    assert item.counterfactual_ids == [
        "cf_1",
        "cf_2",
    ]

    assert item.scenario_instability == "HIGH"
    assert item.reevaluation_required is True


def test_sqlite_persists_reevaluation_triggers(tmp_path):
    from models import (
        DecisionReevaluationTrigger,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        decision_reevaluation_triggers=[
            DecisionReevaluationTrigger(
                trigger_id="trg_test",
                decision_id="dec_test",
                trigger_type=(
                    "TECHNICAL_CONTEXT_CHANGE"
                ),
                source_type="technical_context",
                source_field=(
                    "deployment_environment"
                ),
                source_value="Docker-only",
                affected_candidate_ids=[
                    "cand_a",
                    "cand_b",
                ],
                affected_scenario_ids=[
                    "scn_arch"
                ],
                invalidated_modules=[
                    "integration_assessment",
                    "scenario_analysis",
                ],
                trigger_impact="HIGH",
                reevaluation_required=True,
                rationale=[
                    "Deployment context changed."
                ],
            )
        ]
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)
    restored = store.get(research_id)

    assert restored is not None

    assert len(
        restored.decision_reevaluation_triggers
    ) == 1

    item = (
        restored
        .decision_reevaluation_triggers[0]
    )

    assert item.trigger_id == "trg_test"

    assert (
        item.trigger_type
        == "TECHNICAL_CONTEXT_CHANGE"
    )

    assert (
        item.invalidated_modules
        == [
            "integration_assessment",
            "scenario_analysis",
        ]
    )

    assert item.trigger_impact == "HIGH"
    assert item.reevaluation_required is True


def test_research_gap_search_strategy_round_trip(
    tmp_path,
):
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
            decision_id="dec_strategy",
            research_gaps=[
                ResearchGap(
                    gap_id="gap_strategy",
                    candidate_id="cand_a",
                    criterion_id="crit_scale",
                    gap_type="low_coverage",
                    severity=0.8,
                    description=(
                        "Need scalability evidence"
                    ),
                    suggested_query=(
                        "Qdrant scalability "
                        "official documentation "
                        "benchmark"
                    ),
                    search_strategy=(
                        "PERFORMANCE_SCALE"
                    ),
                    preferred_source_types=[
                        "official_documentation",
                        "benchmark",
                    ],
                    query_qualifiers=[
                        "official documentation",
                        "benchmark",
                    ],
                )
            ],
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)

    restored = store.get(
        research_id
    )

    assert restored is not None
    assert restored.research_analysis is not None

    item = (
        restored
        .research_analysis
        .research_gaps[0]
    )

    assert (
        item.search_strategy
        == "PERFORMANCE_SCALE"
    )

    assert item.preferred_source_types == [
        "official_documentation",
        "benchmark",
    ]

    assert item.query_qualifiers == [
        "official documentation",
        "benchmark",
    ]


def test_source_authority_metadata_round_trip(
    tmp_path,
):
    from models import (
        EvidenceApplicability,
        EvidenceAssessment,
        EvidenceQuality,
        SourceQuality,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    state = SummaryState(
        evidence_assessments=[
            EvidenceAssessment(
                evidence_id="evi_authority",
                decision_id="dec_authority",
                source_quality=SourceQuality(
                    evidence_id=(
                        "evi_authority"
                    ),
                    source_type=(
                        "official_docs"
                    ),
                    confidence=0.9,
                    authority_type=(
                        "OFFICIAL_DOCUMENTATION"
                    ),
                    authority_level="HIGH",
                    authority_signals=[
                        (
                            "candidate_vendor_match:"
                            "cand_qdrant"
                        )
                    ],
                ),
                evidence_quality=EvidenceQuality(
                    evidence_id=(
                        "evi_authority"
                    ),
                    quality_score=0.8,
                    completeness=0.8,
                ),
                applicability=(
                    EvidenceApplicability(
                        evidence_id=(
                            "evi_authority"
                        ),
                        decision_id=(
                            "dec_authority"
                        ),
                        applicability_score=0.8,
                    )
                ),
                overall_score=0.8,
            )
        ]
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(state)

    restored = store.get(
        research_id
    )

    assert restored is not None

    quality = (
        restored
        .evidence_assessments[0]
        .source_quality
    )

    assert (
        quality.authority_type
        == "OFFICIAL_DOCUMENTATION"
    )

    assert (
        quality.authority_level
        == "HIGH"
    )

    assert quality.authority_signals == [
        (
            "candidate_vendor_match:"
            "cand_qdrant"
        )
    ]


def test_research_gap_strategy_match_round_trip(
    tmp_path,
):
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
            decision_id="dec_match",
            research_gaps=[
                ResearchGap(
                    gap_id="gap_match",
                    candidate_id="cand_a",
                    criterion_id="crit_scale",
                    gap_type="low_coverage",
                    severity=0.8,
                    description="Need evidence",
                    suggested_query=(
                        "candidate benchmark"
                    ),
                    search_strategy=(
                        "PERFORMANCE_SCALE"
                    ),
                    preferred_source_types=[
                        "official_documentation",
                        "benchmark",
                    ],
                    strategy_match_status=(
                        "PARTIAL"
                    ),
                    matched_source_types=[
                        "official_documentation",
                    ],
                    missing_source_types=[
                        "benchmark",
                    ],
                    observed_authority_types=[
                        "OFFICIAL_DOCUMENTATION",
                    ],
                    strategy_matched_evidence_ids=[
                        "evi_docs",
                    ],
                )
            ],
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        state
    )

    restored = store.get(
        research_id
    )

    item = (
        restored
        .research_analysis
        .research_gaps[0]
    )

    assert (
        item.strategy_match_status
        == "PARTIAL"
    )

    assert item.matched_source_types == [
        "official_documentation",
    ]

    assert item.missing_source_types == [
        "benchmark",
    ]

    assert (
        item.observed_authority_types
        == ["OFFICIAL_DOCUMENTATION"]
    )

    assert (
        item.strategy_matched_evidence_ids
        == ["evi_docs"]
    )


def test_retrieval_yield_metadata_round_trip(
    tmp_path,
):
    from models import (
        AdaptiveResearchIteration,
        AdaptiveResearchState,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    iteration = AdaptiveResearchIteration(
        decision_id="dec_yield",
        iteration_number=1,
        status="completed",
        retrieval_yield_status=(
            "MODERATE_YIELD"
        ),
        new_evidence_count=3,
        new_authority_types=[
            "ACADEMIC",
        ],
        new_strategy_matches=[
            (
                "cand_a|crit_scale|"
                "academic_paper"
            )
        ],
        gap_count_before=3,
        gap_count_after=2,
        retrieval_yield_reasons=[
            "1 new strategy source match(es)",
        ],
    )

    state = SummaryState(
        adaptive_research_state=(
            AdaptiveResearchState(
                decision_id="dec_yield",
                iteration_count=1,
                iterations=[
                    iteration
                ],
            )
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        state
    )

    restored = store.get(
        research_id
    )

    assert restored is not None

    item = (
        restored
        .adaptive_research_state
        .iterations[0]
    )

    assert (
        item.retrieval_yield_status
        == "MODERATE_YIELD"
    )

    assert item.new_evidence_count == 3

    assert item.new_authority_types == [
        "ACADEMIC"
    ]

    assert item.gap_count_before == 3
    assert item.gap_count_after == 2


def test_evidence_saturation_metadata_round_trip(
    tmp_path,
):
    from models import (
        AdaptiveResearchIteration,
        AdaptiveResearchState,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    iteration = AdaptiveResearchIteration(
        decision_id="dec_saturation",
        iteration_number=1,
        status="completed",
        evidence_saturation_status=(
            "HIGH_SATURATION"
        ),
        new_unique_source_count=2,
        novel_content_count=1,
        duplicate_domain_ratio=0.75,
        near_duplicate_content_ratio=0.8,
        saturation_reasons=[
            (
                "most new evidence is "
                "near-duplicate content"
            )
        ],
    )

    state = SummaryState(
        adaptive_research_state=(
            AdaptiveResearchState(
                decision_id="dec_saturation",
                iteration_count=1,
                iterations=[
                    iteration
                ],
            )
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        state
    )

    restored = store.get(
        research_id
    )

    assert restored is not None

    item = (
        restored
        .adaptive_research_state
        .iterations[0]
    )

    assert (
        item.evidence_saturation_status
        == "HIGH_SATURATION"
    )

    assert (
        item.new_unique_source_count
        == 2
    )

    assert (
        item.novel_content_count
        == 1
    )

    assert (
        item.duplicate_domain_ratio
        == 0.75
    )

    assert (
        item.near_duplicate_content_ratio
        == 0.8
    )


def test_information_gain_metadata_round_trip(
    tmp_path,
):
    from models import (
        AdaptiveResearchIteration,
        AdaptiveResearchState,
        SummaryState,
    )
    from services.research_store import (
        SQLiteResearchStore,
    )

    iteration = AdaptiveResearchIteration(
        decision_id="dec_info_gain",
        iteration_number=1,
        status="completed",
        information_gain_status=(
            "HIGH_INFORMATION_GAIN"
        ),
        new_claim_count=3,
        novel_claim_count=2,
        duplicate_claim_count=1,
        claim_novelty_ratio=0.6667,
        new_directional_signal_count=2,
        new_candidate_criterion_pairs=[
            "cand_a|crit_scale",
        ],
        information_gain_reasons=[
            "1 newly covered candidate×criterion pair(s)",
        ],
    )

    state = SummaryState(
        adaptive_research_state=(
            AdaptiveResearchState(
                decision_id="dec_info_gain",
                iteration_count=1,
                iterations=[
                    iteration
                ],
            )
        )
    )

    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        state
    )

    restored = store.get(
        research_id
    )

    assert restored is not None

    item = (
        restored
        .adaptive_research_state
        .iterations[0]
    )

    assert (
        item.information_gain_status
        == "HIGH_INFORMATION_GAIN"
    )

    assert item.new_claim_count == 3
    assert item.novel_claim_count == 2
    assert item.duplicate_claim_count == 1
    assert item.claim_novelty_ratio == 0.6667

    assert (
        item.new_candidate_criterion_pairs
        == ["cand_a|crit_scale"]
    )
