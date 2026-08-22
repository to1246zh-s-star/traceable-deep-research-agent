from main import _build_research_replay
from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    DecisionReadiness,
    ResearchBudget,
    ResearchStoppingDecision,
    ResearchUsage,
    SensitivityResult,
    SummaryState,
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
