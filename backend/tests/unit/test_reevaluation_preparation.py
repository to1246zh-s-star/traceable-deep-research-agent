import pytest

from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    ReevaluationAssessment,
    ReevaluationPlan,
    ReevaluationReactivationDecision,
    ReevaluationRequest,
    ResearchAnalysis,
    ResearchBudget,
    ResearchGap,
    ResearchStoppingDecision,
    ResearchUsage,
)
import services.reevaluation_preparation as preparation_service
from services.reevaluation_preparation import (
    prepare_reevaluation,
)


def decision():
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


def analysis():
    return ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[],
        status="complete",
    )


def adaptive_state():
    return AdaptiveResearchState(
        decision_id="dec_test",
        status="stopped",
    )


def request():
    return ReevaluationRequest(
        decision_id="dec_test",
    )


def stopping():
    return ResearchStoppingDecision(
        should_continue=False,
        reason="insufficient_marginal_improvement",
        readiness_score=0.6,
        readiness_status="CONFLICTED",
        actionable_gap_count=0,
        blocking_budget_limits=[],
    )


def budget():
    return ResearchBudget(
        max_iterations=3,
        max_tasks=9,
    )


def usage():
    return ResearchUsage(
        iterations=1,
        tasks=3,
    )


def test_real_unknown_path_is_non_actionable():
    result = prepare_reevaluation(
        decision(),
        analysis(),
        adaptive_state(),
        request(),
        [],
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.decision_id == "dec_test"

    assert (
        result.assessment.status
        == "UNKNOWN"
    )

    assert result.plan.status == "UNKNOWN"

    assert result.reevaluation_gaps == []

    assert (
        result.reactivation.eligible
        is False
    )


def test_unknown_path_preserves_original_analysis():
    original = analysis()

    result = prepare_reevaluation(
        decision(),
        original,
        adaptive_state(),
        request(),
        [],
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert result.merged_analysis is original


def test_analysis_decision_id_mismatch_rejected():
    item = analysis()
    item.decision_id = "dec_other"

    with pytest.raises(
        ValueError,
        match="research analysis decision_id",
    ):
        prepare_reevaluation(
            decision(),
            item,
            adaptive_state(),
            request(),
            [],
            research_budget=budget(),
            research_usage=usage(),
            stopping_decision=stopping(),
        )


def test_adaptive_state_decision_id_mismatch_rejected():
    state = adaptive_state()
    state.decision_id = "dec_other"

    with pytest.raises(
        ValueError,
        match="adaptive state decision_id",
    ):
        prepare_reevaluation(
            decision(),
            analysis(),
            state,
            request(),
            [],
            research_budget=budget(),
            research_usage=usage(),
            stopping_decision=stopping(),
        )


def test_request_decision_id_mismatch_rejected():
    item = request()
    item.decision_id = "dec_other"

    with pytest.raises(
        ValueError,
        match="reevaluation request decision_id",
    ):
        prepare_reevaluation(
            decision(),
            analysis(),
            adaptive_state(),
            item,
            [],
            research_budget=budget(),
            research_usage=usage(),
            stopping_decision=stopping(),
        )


def test_facade_composes_services_in_order(
    monkeypatch,
):
    calls = []

    assessment_result = ReevaluationAssessment(
        decision_id="dec_test",
        status="REQUIRED",
        matched_trigger_ids=[
            "trg_test",
        ],
    )

    plan_result = ReevaluationPlan(
        decision_id="dec_test",
        status="REQUIRED",
        research_queries=[
            "updated evidence",
        ],
    )

    gap_result = ResearchGap(
        gap_id="gap_reeval",
        candidate_id="",
        criterion_id="",
        gap_type="reevaluation",
        severity=1.0,
        description="Updated evidence",
        suggested_query="updated evidence",
        status="open",
        priority=3,
    )

    merged_result = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            gap_result,
        ],
        status="gaps_detected",
    )

    reactivation_result = (
        ReevaluationReactivationDecision(
            decision_id="dec_test",
            status="ELIGIBLE",
            eligible=True,
            actionable_gap_ids=[
                "gap_reeval",
            ],
        )
    )

    def fake_assess(req, triggers):
        calls.append("assess")
        return assessment_result

    def fake_plan(dec, assessment, triggers):
        calls.append("plan")
        assert assessment is assessment_result
        return plan_result

    def fake_build_gaps(dec, plan):
        calls.append("gaps")
        assert plan is plan_result
        return [
            gap_result,
        ]

    def fake_merge(current, gaps):
        calls.append("merge")
        assert gaps == [
            gap_result,
        ]
        return merged_result

    def fake_reactivation(
        plan,
        gaps,
        state,
        *,
        research_budget,
        research_usage,
        stopping_decision,
    ):
        calls.append("reactivation")

        assert plan is plan_result
        assert gaps == [
            gap_result,
        ]

        return reactivation_result

    monkeypatch.setattr(
        preparation_service,
        "assess_reevaluation_need",
        fake_assess,
    )

    monkeypatch.setattr(
        preparation_service,
        "build_reevaluation_plan",
        fake_plan,
    )

    monkeypatch.setattr(
        preparation_service,
        "build_reevaluation_research_gaps",
        fake_build_gaps,
    )

    monkeypatch.setattr(
        preparation_service,
        "merge_reevaluation_research_gaps",
        fake_merge,
    )

    monkeypatch.setattr(
        preparation_service,
        "assess_reevaluation_reactivation",
        fake_reactivation,
    )

    result = prepare_reevaluation(
        decision(),
        analysis(),
        adaptive_state(),
        request(),
        [],
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert calls == [
        "assess",
        "plan",
        "gaps",
        "merge",
        "reactivation",
    ]

    assert (
        result.assessment
        is assessment_result
    )

    assert result.plan is plan_result

    assert (
        result.merged_analysis
        is merged_result
    )

    assert (
        result.reactivation
        is reactivation_result
    )


def test_reactivation_receives_only_new_reevaluation_gaps(
    monkeypatch,
):
    old_gap = ResearchGap(
        gap_id="gap_old",
        candidate_id="cand_a",
        criterion_id="crit_a",
        gap_type="low_coverage",
        severity=0.5,
        description="Old gap",
        suggested_query="old query",
    )

    new_gap = ResearchGap(
        gap_id="gap_new",
        candidate_id="",
        criterion_id="",
        gap_type="reevaluation",
        severity=1.0,
        description="New gap",
        suggested_query="new query",
        priority=3,
    )

    current_analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            old_gap,
        ],
        status="gaps_detected",
    )

    assessment_result = ReevaluationAssessment(
        decision_id="dec_test",
        status="REQUIRED",
    )

    plan_result = ReevaluationPlan(
        decision_id="dec_test",
        status="REQUIRED",
    )

    captured = {}

    monkeypatch.setattr(
        preparation_service,
        "assess_reevaluation_need",
        lambda req, triggers: assessment_result,
    )

    monkeypatch.setattr(
        preparation_service,
        "build_reevaluation_plan",
        lambda dec, assessment, triggers: plan_result,
    )

    monkeypatch.setattr(
        preparation_service,
        "build_reevaluation_research_gaps",
        lambda dec, plan: [new_gap],
    )

    def fake_reactivation(
        plan,
        gaps,
        state,
        **kwargs,
    ):
        captured["gaps"] = list(gaps)

        return ReevaluationReactivationDecision(
            decision_id="dec_test",
            status="ELIGIBLE",
            eligible=True,
            actionable_gap_ids=[
                "gap_new",
            ],
        )

    monkeypatch.setattr(
        preparation_service,
        "assess_reevaluation_reactivation",
        fake_reactivation,
    )

    result = prepare_reevaluation(
        decision(),
        current_analysis,
        adaptive_state(),
        request(),
        [],
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert captured["gaps"] == [
        new_gap,
    ]

    assert [
        gap.gap_id
        for gap
        in result.merged_analysis.research_gaps
    ] == [
        "gap_old",
        "gap_new",
    ]


def test_preparation_does_not_reactivate_adaptive_state():
    state = adaptive_state()

    original_status = state.status

    prepare_reevaluation(
        decision(),
        analysis(),
        state,
        request(),
        [],
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert state.status == original_status


def test_preparation_does_not_mutate_stopping_decision():
    stop = stopping()

    original_continue = stop.should_continue
    original_reason = stop.reason

    prepare_reevaluation(
        decision(),
        analysis(),
        adaptive_state(),
        request(),
        [],
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stop,
    )

    assert (
        stop.should_continue
        == original_continue
    )

    assert stop.reason == original_reason


def test_preparation_does_not_expose_decision_outputs():
    result = prepare_reevaluation(
        decision(),
        analysis(),
        adaptive_state(),
        request(),
        [],
        research_budget=budget(),
        research_usage=usage(),
        stopping_decision=stopping(),
    )

    assert not hasattr(
        result,
        "candidate_scores",
    )

    assert not hasattr(
        result,
        "recommendation",
    )

    assert not hasattr(
        result,
        "predicted_winner_id",
    )
