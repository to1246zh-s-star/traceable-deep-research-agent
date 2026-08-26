from main import _build_research_replay
from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    DecisionReadiness,
    IntegrationAssessment,
    ResearchBudget,
    ResearchStoppingDecision,
    ResearchUsage,
    SensitivityResult,
    SummaryState,
    TechnicalContext,
)


def test_replay_returns_null_decision_for_non_decision_research():
    state = SummaryState(
        research_topic="Explain transformer attention",
    )

    payload = _build_research_replay(
        "research_non_decision",
        state,
    )

    assert payload["decision"] is None


def test_replay_exposes_decision_intelligence_state():
    decision = DecisionCase(
        decision_id="dec_api",
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

    state = SummaryState(
        research_topic="A vs B",
        decision_case=decision,
        decision_sensitivity=[
            SensitivityResult(
                decision_id="dec_api",
                criterion_id="crit_scale",
                baseline_weight=0.30,
                baseline_winner_id="cand_a",
                score_margin_before=0.60,
                recommendation_changes=True,
                switch_threshold=0.38,
                weight_delta=0.08,
                direction_of_change="increase",
                competing_candidate_id="cand_b",
                score_margin_after=-0.04,
            )
        ],
        decision_readiness=DecisionReadiness(
            decision_id="dec_api",
            overall_score=0.72,
            status="TENTATIVE",
            criterion_coverage=0.8,
            evidence_quality=0.7,
            applicability=0.75,
            agreement_score=0.65,
            decision_margin=0.4,
        ),
        stopping_decision=ResearchStoppingDecision(
            should_continue=True,
            reason="research_needed",
            readiness_score=0.72,
            readiness_status="TENTATIVE",
            readiness_improvement=0.1,
            actionable_gap_count=2,
            blocking_budget_limits=[],
        ),
        research_budget=ResearchBudget(
            max_iterations=3,
            max_tasks=9,
        ),
        research_usage=ResearchUsage(
            iterations=1,
            tasks=2,
            semantic_llm_calls=3,
            constraint_llm_calls=2,
        ),
        adaptive_research_state=AdaptiveResearchState(
            decision_id="dec_api",
            iteration_count=1,
        ),
    )

    payload = _build_research_replay(
        "research_decision",
        state,
    )

    decision_payload = payload["decision"]

    assert decision_payload is not None

    assert (
        decision_payload["case"]["decision_id"]
        == "dec_api"
    )

    assert (
        decision_payload["case"]["question"]
        == "Choose A or B"
    )

    assert (
        decision_payload["readiness"]["status"]
        == "TENTATIVE"
    )

    assert (
        decision_payload["readiness"]["overall_score"]
        == 0.72
    )

    assert (
        decision_payload["stopping_decision"][
            "should_continue"
        ]
        is True
    )

    assert (
        decision_payload["research_usage"]["iterations"]
        == 1
    )

    assert (
        decision_payload["research_usage"]["tasks"]
        == 2
    )
    assert (
        decision_payload["research_usage"]["semantic_llm_calls"]
        == 3
    )
    assert (
        decision_payload["research_usage"]["constraint_llm_calls"]
        == 2
    )

    assert (
        decision_payload["adaptive_research_state"][
            "iteration_count"
        ]
        == 1
    )


def test_replay_decision_payload_is_json_safe():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_json",
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
    )

    payload = _build_research_replay(
        "research_json",
        state,
    )

    decision_payload = payload["decision"]

    assert isinstance(
        decision_payload,
        dict,
    )

    assert isinstance(
        decision_payload["case"],
        dict,
    )

    assert isinstance(
        decision_payload["case"]["candidates"],
        list,
    )

    assert isinstance(
        decision_payload["case"]["candidates"][0],
        dict,
    )


def test_replay_exposes_decision_sensitivity():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_sensitivity_api",
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
        decision_sensitivity=[
            SensitivityResult(
                decision_id="dec_sensitivity_api",
                criterion_id="crit_scale",
                baseline_weight=0.30,
                baseline_winner_id="cand_a",
                score_margin_before=0.60,
                recommendation_changes=True,
                switch_threshold=0.38,
                weight_delta=0.08,
                direction_of_change="increase",
                competing_candidate_id="cand_b",
                score_margin_after=-0.04,
            )
        ],
    )

    payload = _build_research_replay(
        "research_sensitivity",
        state,
    )

    decision_payload = payload["decision"]

    assert decision_payload is not None
    assert len(decision_payload["sensitivity"]) == 1

    sensitivity = decision_payload["sensitivity"][0]

    assert sensitivity["decision_id"] == "dec_sensitivity_api"
    assert sensitivity["criterion_id"] == "crit_scale"
    assert sensitivity["baseline_weight"] == 0.30
    assert sensitivity["baseline_winner_id"] == "cand_a"
    assert sensitivity["score_margin_before"] == 0.60
    assert sensitivity["recommendation_changes"] is True
    assert sensitivity["switch_threshold"] == 0.38
    assert sensitivity["weight_delta"] == 0.08
    assert sensitivity["direction_of_change"] == "increase"
    assert sensitivity["competing_candidate_id"] == "cand_b"
    assert sensitivity["score_margin_after"] == -0.04


def test_replay_uses_empty_sensitivity_list_by_default():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_empty_sensitivity",
            question="Choose A or B",
        ),
    )

    payload = _build_research_replay(
        "research_empty_sensitivity",
        state,
    )

    assert payload["decision"] is not None
    assert payload["decision"]["sensitivity"] == []


def test_replay_exposes_architecture_context():
    decision = DecisionCase(
        decision_id="dec_architecture_api",
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

    state = SummaryState(
        research_topic="Architecture-aware choice",
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
                "limited DevOps capacity",
            ],
        ),
        integration_assessments=[
            IntegrationAssessment(
                decision_id=decision.decision_id,
                candidate_id="cand_b",
                integration_complexity="MEDIUM",
                migration_complexity="MEDIUM",
                operational_change="HIGH",
                infrastructure_change="MEDIUM",
                required_new_dependencies=[
                    "coordination service",
                ],
                team_skill_gaps=[
                    "distributed operations",
                ],
                evidence_ids=[
                    "evi_architecture",
                ],
            )
        ],
    )

    payload = _build_research_replay(
        "research_architecture",
        state,
    )

    decision_payload = payload["decision"]

    assert decision_payload is not None

    context = decision_payload["technical_context"]

    assert context["existing_stack"] == [
        "Python",
        "FastAPI",
    ]
    assert context["deployment_environment"] == [
        "Docker-only",
    ]

    assessments = decision_payload[
        "integration_assessments"
    ]

    assert len(assessments) == 1
    assert assessments[0]["candidate_id"] == "cand_b"
    assert (
        assessments[0]["integration_complexity"]
        == "MEDIUM"
    )
    assert assessments[0]["operational_change"] == "HIGH"


def test_replay_uses_empty_architecture_defaults():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_empty_architecture",
            question="Choose A or B",
        ),
    )

    payload = _build_research_replay(
        "research_empty_architecture",
        state,
    )

    decision_payload = payload["decision"]

    assert decision_payload is not None
    assert decision_payload["technical_context"] is None
    assert decision_payload["integration_assessments"] == []


def test_replay_exposes_recommendation_robustness():
    from main import (
        _serialize_decision_intelligence,
    )
    from models import (
        DecisionCase,
        RecommendationRobustness,
        SummaryState,
    )

    state = SummaryState(
        decision_case=DecisionCase(
            decision_id="dec_robust",
            question="Choose A or B",
        ),
        recommendation_robustness=(
            RecommendationRobustness(
                decision_id="dec_robust",
                baseline_winner_id="cand_a",
                status="ROBUST",
                score_margin=1.2,
                tested_criteria_count=2,
                flip_count=0,
                reasons=[
                    "No tested perturbation changed the winner."
                ],
            )
        ),
    )

    payload = _serialize_decision_intelligence(
        state
    )

    assert payload is not None
    assert payload["robustness"] is not None

    robustness = payload["robustness"]

    assert robustness["status"] == "ROBUST"
    assert (
        robustness["baseline_winner_id"]
        == "cand_a"
    )
    assert robustness["flip_count"] == 0



def test_replay_exposes_adaptive_research_value_explanation():
    from models import AdaptiveResearchIteration

    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_adaptive_replay",
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
            decision_id="dec_adaptive_replay",
            iteration_count=1,
            iterations=[
                AdaptiveResearchIteration(
                    decision_id="dec_adaptive_replay",
                    iteration_number=1,
                    status="completed",
                    retrieval_yield_status="LOW_YIELD",
                    new_evidence_count=6,
                    evidence_saturation_status="HIGH_SATURATION",
                    new_unique_source_count=5,
                    novel_content_count=1,
                    duplicate_domain_ratio=0.83,
                    near_duplicate_content_ratio=0.67,
                    information_gain_status="NO_INFORMATION_GAIN",
                    new_claim_count=2,
                    novel_claim_count=1,
                    duplicate_claim_count=1,
                    claim_novelty_ratio=0.5,
                    new_directional_signal_count=0,
                    new_candidate_criterion_pairs=[],
                    adaptive_research_value_status="LOW_VALUE",
                    research_value_summary=(
                        "This research iteration added limited "
                        "decision-relevant value."
                    ),
                    research_value_explanation=[
                        "retrieval yield: low_yield",
                        "evidence saturation: high_saturation",
                        (
                            "decision information gain: "
                            "no_information_gain"
                        ),
                        "adaptive research value: low_value",
                    ],
                    research_value_observations=[
                        "6 new evidence item(s)",
                        "5 new unique source URL(s)",
                        "1 novel claim(s)",
                    ],
                    stopping_explanation=(
                        "Adaptive research stopped because marginal "
                        "research value showed diminishing returns "
                        "across 2 consecutive low-value iteration(s)."
                    ),
                )
            ],
        ),
    )

    payload = _build_research_replay(
        "research_adaptive_replay",
        state,
    )

    decision = payload["decision"]
    assert decision is not None

    adaptive = decision[
        "adaptive_research_state"
    ]

    assert adaptive["iteration_count"] == 1

    item = adaptive["iterations"][0]

    # Phase 29
    assert (
        item["retrieval_yield_status"]
        == "LOW_YIELD"
    )
    assert item["new_evidence_count"] == 6

    # Phase 30
    assert (
        item["evidence_saturation_status"]
        == "HIGH_SATURATION"
    )
    assert (
        item["near_duplicate_content_ratio"]
        == 0.67
    )

    # Phase 31
    assert (
        item["information_gain_status"]
        == "NO_INFORMATION_GAIN"
    )
    assert item["novel_claim_count"] == 1
    assert (
        item["new_candidate_criterion_pairs"]
        == []
    )

    # Phase 32
    assert (
        item["adaptive_research_value_status"]
        == "LOW_VALUE"
    )

    # Phase 33
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


def test_replay_preserves_adaptive_iteration_order():
    from models import AdaptiveResearchIteration

    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_order",
            question="Choose A or B",
        ),
        adaptive_research_state=AdaptiveResearchState(
            decision_id="dec_order",
            iteration_count=3,
            iterations=[
                AdaptiveResearchIteration(
                    decision_id="dec_order",
                    iteration_number=1,
                    status="completed",
                    adaptive_research_value_status="HIGH_VALUE",
                    research_value_summary="iteration one",
                ),
                AdaptiveResearchIteration(
                    decision_id="dec_order",
                    iteration_number=2,
                    status="completed",
                    adaptive_research_value_status="MODERATE_VALUE",
                    research_value_summary="iteration two",
                ),
                AdaptiveResearchIteration(
                    decision_id="dec_order",
                    iteration_number=3,
                    status="completed",
                    adaptive_research_value_status="LOW_VALUE",
                    research_value_summary="iteration three",
                ),
            ],
        ),
    )

    payload = _build_research_replay(
        "research_order",
        state,
    )

    iterations = payload[
        "decision"
    ][
        "adaptive_research_state"
    ][
        "iterations"
    ]

    assert [
        item["iteration_number"]
        for item in iterations
    ] == [
        1,
        2,
        3,
    ]

    assert [
        item["research_value_summary"]
        for item in iterations
    ] == [
        "iteration one",
        "iteration two",
        "iteration three",
    ]


def test_replay_exposes_safe_defaults_for_legacy_adaptive_iteration():
    from models import AdaptiveResearchIteration

    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_legacy",
            question="Choose A or B",
        ),
        adaptive_research_state=AdaptiveResearchState(
            decision_id="dec_legacy",
            iteration_count=1,
            iterations=[
                AdaptiveResearchIteration(
                    decision_id="dec_legacy",
                    iteration_number=1,
                )
            ],
        ),
    )

    payload = _build_research_replay(
        "research_legacy",
        state,
    )

    item = payload[
        "decision"
    ][
        "adaptive_research_state"
    ][
        "iterations"
    ][0]

    assert (
        item["retrieval_yield_status"]
        == "UNKNOWN"
    )

    assert (
        item["evidence_saturation_status"]
        == "UNKNOWN"
    )

    assert (
        item["information_gain_status"]
        == "UNKNOWN"
    )

    assert (
        item["adaptive_research_value_status"]
        == "UNKNOWN"
    )

    assert item["research_value_summary"] == ""
    assert item["research_value_explanation"] == []
    assert item["research_value_observations"] == []
    assert item["stopping_explanation"] == ""


def test_replay_serialization_does_not_mutate_adaptive_state():
    from models import AdaptiveResearchIteration

    iteration = AdaptiveResearchIteration(
        decision_id="dec_no_mutation",
        iteration_number=1,
        status="completed",
        adaptive_research_value_status="LOW_VALUE",
        research_value_summary="persisted summary",
        research_value_explanation=[
            "persisted explanation"
        ],
        research_value_observations=[
            "persisted observation"
        ],
        stopping_explanation=(
            "persisted stopping explanation"
        ),
    )

    state = SummaryState(
        research_topic="A vs B",
        decision_case=DecisionCase(
            decision_id="dec_no_mutation",
            question="Choose A or B",
        ),
        adaptive_research_state=AdaptiveResearchState(
            decision_id="dec_no_mutation",
            iteration_count=1,
            iterations=[
                iteration
            ],
        ),
    )

    _build_research_replay(
        "research_no_mutation",
        state,
    )

    assert (
        iteration.adaptive_research_value_status
        == "LOW_VALUE"
    )

    assert (
        iteration.research_value_summary
        == "persisted summary"
    )

    assert (
        iteration.research_value_explanation
        == ["persisted explanation"]
    )

    assert (
        iteration.research_value_observations
        == ["persisted observation"]
    )

    assert (
        iteration.stopping_explanation
        == "persisted stopping explanation"
    )
