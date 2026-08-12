"""Orchestration layer for the V3 decision-intelligence pipeline."""

from models import (
    CandidateCriterionScore,
    DecisionCase,
    DecisionComparison,
    EvidenceAssessment,
    EvidenceSignal,
    ReadinessSnapshot,
    ResearchBudget,
    ResearchUsage,
    SummaryState,
)
from services.decision_comparison import compare_candidates
from services.decision_evaluator import evaluate_decision_case
from services.decision_input_builder import (
    build_candidate_criterion_scores,
    build_evidence_assessments,
    build_evidence_signals,
)
from services.decision_readiness import calculate_readiness
from services.research_analysis import analyze_research
from services.research_stopping import should_continue_research


def run_decision_pipeline(
    state: SummaryState,
    decision: DecisionCase,
    *,
    constraint_results: dict[str, dict[str, bool]] | None = None,
    criterion_scores: list[CandidateCriterionScore] | None = None,
    evidence_signals: list[EvidenceSignal] | None = None,
    evidence_assessments: list[EvidenceAssessment] | None = None,
    research_budget: ResearchBudget | None = None,
    research_usage: ResearchUsage | None = None,
) -> SummaryState:
    """
    Run one deterministic V3 decision evaluation pass.

    This function does not generate decision inputs with an LLM.
    It only orchestrates the existing Phase 7-14 services and stores
    their outputs on SummaryState.
    """

    if evidence_assessments is None:
        evidence_assessments = build_evidence_assessments(
            state,
            decision,
        )

    state.evidence_assessments = evidence_assessments

    if evidence_signals is None:
        evidence_signals = build_evidence_signals(
            state,
            decision,
        )

    state.evidence_signals = evidence_signals

    if criterion_scores is None:
        criterion_scores = build_candidate_criterion_scores(
            decision,
            evidence_signals,
        )

    budget = research_budget or ResearchBudget()
    usage = research_usage or ResearchUsage()

    evaluation = evaluate_decision_case(
        decision,
        constraint_results=constraint_results,
    )

    try:
        comparison = compare_candidates(
            decision,
            evaluation,
            criterion_scores,
        )
    except ValueError as exc:
        if "missing score for candidate" not in str(exc):
            raise

        comparison = DecisionComparison(
            decision_id=decision.decision_id,
            status="incomplete",
            excluded_candidate_ids=list(
                evaluation.disqualified_candidate_ids
            ),
            unresolved_candidate_ids=list(
                evaluation.unresolved_candidate_ids
            ),
        )

    analysis = analyze_research(
        decision,
        evidence_signals,
    )

    readiness = calculate_readiness(
        decision,
        comparison,
        analysis,
        evidence_assessments,
    )

    history = list(state.readiness_history)

    history.append(
        ReadinessSnapshot(
            iteration_number=len(history) + 1,
            overall_score=readiness.overall_score,
            status=readiness.status,
        )
    )

    stopping_decision = should_continue_research(
        readiness,
        analysis,
        budget,
        usage,
        readiness_history=history,
    )

    state.decision_case = decision
    state.decision_evaluation = evaluation
    state.decision_comparison = comparison

    state.evidence_signals = list(evidence_signals)
    state.evidence_assessments = list(evidence_assessments)

    state.research_analysis = analysis
    state.decision_readiness = readiness

    state.research_budget = budget
    state.research_usage = usage
    state.readiness_history = history
    state.stopping_decision = stopping_decision

    return state
