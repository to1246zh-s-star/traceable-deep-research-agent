import pytest

from models import (
    Candidate,
    CandidateDecisionResult,
    Constraint,
    DecisionCase,
    DecisionEvaluation,
    DecisionReadiness,
    SummaryState,
    TechnicalContext,
    TodoItem,
)
from services.reporter import ReportingService


class Config:
    strip_thinking_tokens = False


class RecordingAgent:
    def __init__(self):
        self.prompt = ""

    def run(self, prompt):
        self.prompt = prompt
        return "report"

    def clear_history(self):
        pass


def state_with_constraint(status):
    candidate = Candidate(candidate_id="cand_mongodb", name="MongoDB")
    constraint = Constraint(
        constraint_id="con_transactions",
        text="Must satisfy strong multi-document transaction consistency",
    )
    decision = DecisionCase(
        decision_id="dec_grounded",
        question="PostgreSQL or MongoDB?",
        candidates=[candidate],
        constraints=[constraint],
    )

    missing = [constraint.constraint_id] if status == "UNKNOWN" else []
    violated = [constraint.constraint_id] if status == "UNSATISFIED" else []

    return SummaryState(
        research_topic=decision.question,
        decision_case=decision,
        decision_evaluation=DecisionEvaluation(
            decision_id=decision.decision_id,
            status="incomplete" if status == "UNKNOWN" else "complete",
            candidate_results=[
                CandidateDecisionResult(
                    candidate_id=candidate.candidate_id,
                    status={
                        "UNKNOWN": "unresolved",
                        "SATISFIED": "eligible",
                        "UNSATISFIED": "disqualified",
                    }[status],
                    missing_constraint_ids=missing,
                    violated_constraint_ids=violated,
                )
            ],
        ),
        decision_readiness=DecisionReadiness(
            decision_id=decision.decision_id,
            overall_score=0.5,
            status="NOT_READY",
            criterion_coverage=0.2,
            evidence_quality=0.2,
            applicability=0.5,
            agreement_score=0.5,
            decision_margin=0.0,
        ),
        todo_items=[
            TodoItem(
                id=1,
                title="Transactions",
                intent="Research transactions",
                query="MongoDB transactions",
                status="completed",
                summary=(
                    "MongoDB only supports single-document ACID and does "
                    "not support cross-document transactions"
                ),
            )
        ],
    )


@pytest.mark.parametrize("status", ["UNKNOWN", "SATISFIED", "UNSATISFIED"])
def test_constraint_status_is_rendered_canonically(status):
    agent = RecordingAgent()
    ReportingService(agent, Config()).generate_report(
        state_with_constraint(status)
    )

    assert f'"status":"{status}"' in agent.prompt


def test_unknown_structured_state_has_precedence_over_narrative_denial():
    agent = RecordingAgent()
    ReportingService(agent, Config()).generate_report(
        state_with_constraint("UNKNOWN")
    )

    assert "AUTHORITATIVE STRUCTURED STATE" in agent.prompt
    assert "NON-AUTHORITATIVE RESEARCH NARRATIVE" in agent.prompt
    assert "UNKNOWN must remain UNKNOWN" in agent.prompt
    assert "Missing evidence is not evidence of absence" in agent.prompt
    assert "only supports single-document ACID" in agent.prompt
    assert "ignore narrative and preserve structured status" in agent.prompt


def test_user_technical_context_is_available_as_context_fact():
    state = state_with_constraint("UNKNOWN")
    state.technical_context = TechnicalContext(
        team_capabilities=["team knows PostgreSQL"]
    )
    agent = RecordingAgent()

    ReportingService(agent, Config()).generate_report(state)

    assert "USER_PROVIDED_CONTEXT" in agent.prompt
    assert "team knows PostgreSQL" in agent.prompt
    assert "must be labeled as inference" in agent.prompt


def test_decision_without_readiness_still_gets_grounding_contract():
    state = state_with_constraint("UNKNOWN")
    state.decision_readiness = None
    agent = RecordingAgent()

    ReportingService(agent, Config()).generate_report(state)

    assert "Readiness status: UNKNOWN" in agent.prompt
    assert "AUTHORITATIVE STRUCTURED STATE" in agent.prompt
