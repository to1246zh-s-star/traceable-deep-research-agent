import pytest

from models import (
    DecisionReadiness,
    ReadinessSnapshot,
    ResearchAnalysis,
    ResearchBudget,
    ResearchGap,
    ResearchUsage,
)
from services.research_stopping import (
    budget_limit_violations,
    calculate_readiness_improvement,
    should_continue_research,
)


def readiness(
    *,
    score=0.60,
    status="TENTATIVE",
):
    return DecisionReadiness(
        decision_id="dec_test",
        overall_score=score,
        status=status,
        criterion_coverage=score,
        evidence_quality=score,
        applicability=score,
        agreement_score=score,
        decision_margin=score,
    )


def analysis_with_gap():
    return ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            ResearchGap(
                gap_id="gap_test",
                candidate_id="cand_test",
                criterion_id="crit_test",
                gap_type="low_coverage",
                severity=0.8,
                description="Need more evidence",
                suggested_query="Qdrant reliability benchmark",
            )
        ],
    )


def test_ready_decision_stops_immediately():
    decision = should_continue_research(
        readiness(
            score=0.85,
            status="READY",
        ),
        analysis_with_gap(),
        ResearchBudget(),
        ResearchUsage(),
    )

    assert decision.should_continue is False
    assert decision.reason == "decision_ready"


def test_budget_exhaustion_stops_research():
    budget = ResearchBudget(
        max_iterations=3,
        max_tasks=5,
    )

    usage = ResearchUsage(
        iterations=3,
        tasks=2,
    )

    decision = should_continue_research(
        readiness(),
        analysis_with_gap(),
        budget,
        usage,
    )

    assert decision.should_continue is False
    assert decision.reason == "budget_exhausted"
    assert "max_iterations" in decision.blocking_budget_limits


def test_task_budget_exhaustion_is_detected():
    budget = ResearchBudget(
        max_iterations=3,
        max_tasks=5,
    )

    usage = ResearchUsage(
        iterations=1,
        tasks=5,
    )

    violations = budget_limit_violations(
        budget,
        usage,
    )

    assert "max_tasks" in violations


def test_optional_search_budget_is_detected():
    budget = ResearchBudget(
        max_searches=10,
    )

    usage = ResearchUsage(
        searches=10,
    )

    violations = budget_limit_violations(
        budget,
        usage,
    )

    assert "max_searches" in violations


def test_no_actionable_gap_stops_research():
    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[],
    )

    decision = should_continue_research(
        readiness(),
        analysis,
        ResearchBudget(),
        ResearchUsage(),
    )

    assert decision.should_continue is False
    assert decision.reason == "no_actionable_gaps"


def test_readiness_improvement_uses_last_two_snapshots():
    history = [
        ReadinessSnapshot(
            iteration_number=1,
            overall_score=0.50,
            status="INSUFFICIENT_EVIDENCE",
        ),
        ReadinessSnapshot(
            iteration_number=2,
            overall_score=0.65,
            status="TENTATIVE",
        ),
    ]

    assert calculate_readiness_improvement(
        history
    ) == pytest.approx(0.15)


def test_small_marginal_improvement_stops_research():
    history = [
        ReadinessSnapshot(
            iteration_number=1,
            overall_score=0.60,
            status="TENTATIVE",
        ),
        ReadinessSnapshot(
            iteration_number=2,
            overall_score=0.61,
            status="TENTATIVE",
        ),
    ]

    decision = should_continue_research(
        readiness(
            score=0.61,
            status="TENTATIVE",
        ),
        analysis_with_gap(),
        ResearchBudget(),
        ResearchUsage(
            iterations=2,
            tasks=3,
        ),
        readiness_history=history,
        min_readiness_improvement=0.02,
    )

    assert decision.should_continue is False
    assert decision.reason == "insufficient_marginal_improvement"
    assert decision.readiness_improvement == pytest.approx(0.01)


def test_meaningful_improvement_with_gap_continues_research():
    history = [
        ReadinessSnapshot(
            iteration_number=1,
            overall_score=0.50,
            status="INSUFFICIENT_EVIDENCE",
        ),
        ReadinessSnapshot(
            iteration_number=2,
            overall_score=0.60,
            status="TENTATIVE",
        ),
    ]

    decision = should_continue_research(
        readiness(
            score=0.60,
            status="TENTATIVE",
        ),
        analysis_with_gap(),
        ResearchBudget(),
        ResearchUsage(
            iterations=2,
            tasks=3,
        ),
        readiness_history=history,
    )

    assert decision.should_continue is True
    assert decision.reason == "continue_research"


def test_first_iteration_can_continue_without_history():
    decision = should_continue_research(
        readiness(),
        analysis_with_gap(),
        ResearchBudget(),
        ResearchUsage(),
        readiness_history=[],
    )

    assert decision.should_continue is True
    assert decision.readiness_improvement is None


def test_retrieval_yield_fields_have_safe_defaults():
    decision = should_continue_research(
        readiness(
            score=0.5,
            status="NOT_READY",
        ),
        analysis_with_gap(),
        ResearchBudget(),
        ResearchUsage(),
    )

    assert (
        decision.retrieval_yield_status
        == "UNKNOWN"
    )

    assert (
        decision
        .consecutive_low_yield_iterations
        == 0
    )


def test_adaptive_research_value_fields_have_safe_defaults():
    decision = should_continue_research(
        readiness(
            score=0.5,
            status="NOT_READY",
        ),
        analysis_with_gap(),
        ResearchBudget(),
        ResearchUsage(),
    )

    assert (
        decision.adaptive_research_value_status
        == "UNKNOWN"
    )

    assert (
        decision.consecutive_low_value_iterations
        == 0
    )
