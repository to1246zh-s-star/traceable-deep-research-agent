"""Deterministic orchestration facade for decision re-evaluation preparation."""

from __future__ import annotations

from models import (
    AdaptiveResearchState,
    DecisionCase,
    DecisionReevaluationTrigger,
    ReevaluationPreparation,
    ReevaluationRequest,
    ResearchAnalysis,
    ResearchBudget,
    ResearchStoppingDecision,
    ResearchUsage,
)
from services.reevaluation_analysis_merge import (
    merge_reevaluation_research_gaps,
)
from services.reevaluation_assessor import (
    assess_reevaluation_need,
)
from services.reevaluation_gap_bridge import (
    build_reevaluation_research_gaps,
)
from services.reevaluation_planner import (
    build_reevaluation_plan,
)
from services.reevaluation_reactivation import (
    assess_reevaluation_reactivation,
)


def prepare_reevaluation(
    decision: DecisionCase,
    analysis: ResearchAnalysis,
    adaptive_state: AdaptiveResearchState,
    request: ReevaluationRequest,
    triggers: list[DecisionReevaluationTrigger],
    *,
    research_budget: ResearchBudget | None,
    research_usage: ResearchUsage | None,
    stopping_decision: ResearchStoppingDecision | None,
) -> ReevaluationPreparation:
    """
    Prepare one deterministic decision re-evaluation.

    Pipeline:

    request
    -> assessment
    -> plan
    -> reevaluation gaps
    -> merged research analysis
    -> adaptive reactivation eligibility

    This function deliberately does NOT:
    - perform retrieval;
    - create TodoItem objects;
    - call an LLM;
    - execute the adaptive research loop;
    - reactivate AdaptiveResearchState;
    - mutate ResearchStoppingDecision;
    - create candidate scores;
    - predict a winner;
    - change recommendation;
    - mutate historical replay / ADR state.
    """

    _validate_decision_ids(
        decision,
        analysis,
        adaptive_state,
        request,
    )

    assessment = assess_reevaluation_need(
        request,
        triggers,
    )

    plan = build_reevaluation_plan(
        decision,
        assessment,
        triggers,
    )

    reevaluation_gaps = (
        build_reevaluation_research_gaps(
            decision,
            plan,
        )
    )

    merged_analysis = (
        merge_reevaluation_research_gaps(
            analysis,
            reevaluation_gaps,
        )
    )

    reactivation = (
        assess_reevaluation_reactivation(
            plan,
            reevaluation_gaps,
            adaptive_state,
            research_budget=research_budget,
            research_usage=research_usage,
            stopping_decision=stopping_decision,
        )
    )

    return ReevaluationPreparation(
        decision_id=decision.decision_id,
        assessment=assessment,
        plan=plan,
        reevaluation_gaps=list(
            reevaluation_gaps
        ),
        merged_analysis=merged_analysis,
        reactivation=reactivation,
    )


def _validate_decision_ids(
    decision: DecisionCase,
    analysis: ResearchAnalysis,
    adaptive_state: AdaptiveResearchState,
    request: ReevaluationRequest,
) -> None:
    decision_id = decision.decision_id

    if analysis.decision_id != decision_id:
        raise ValueError(
            "research analysis decision_id "
            "does not match decision"
        )

    if adaptive_state.decision_id != decision_id:
        raise ValueError(
            "adaptive state decision_id "
            "does not match decision"
        )

    if request.decision_id != decision_id:
        raise ValueError(
            "reevaluation request decision_id "
            "does not match decision"
        )
