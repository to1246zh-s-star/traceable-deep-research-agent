from models import (
    Candidate,
    DecisionCase,
    DecisionReadiness,
    ResearchStoppingDecision,
    SummaryState,
    TodoItem,
)
from services.reporter import ReportingService


class FakeConfig:
    strip_thinking_tokens = False


class RecordingAgent:
    def __init__(self):
        self.prompts = []
        self.clear_calls = 0

    def run(self, prompt):
        self.prompts.append(prompt)
        return "# Report\nprovisional result"

    def clear_history(self):
        self.clear_calls += 1


def make_state(status):
    decision = DecisionCase(
        decision_id="dec_reporter",
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
        decision_readiness=DecisionReadiness(
            decision_id="dec_reporter",
            overall_score=0.6,
            status=status,
            criterion_coverage=0.9,
            evidence_quality=0.7,
            applicability=0.3,
            agreement_score=0.7,
            decision_margin=0.1,
            blocking_reasons=[
                "important evidence conflicts remain unresolved",
            ],
        ),
        stopping_decision=ResearchStoppingDecision(
            should_continue=False,
            reason="budget_exhausted",
            readiness_score=0.6,
            readiness_status=status,
            actionable_gap_count=4,
            blocking_budget_limits=[
                "max_iterations"
            ],
        ),
        todo_items=[
            TodoItem(
                id=1,
                title="Research A vs B",
                intent="Compare candidates",
                query="A vs B",
                status="completed",
                summary="Evidence summary",
                sources_summary="Source summary",
            )
        ],
    )

    return state


def test_conflicted_report_prompt_contains_provisional_policy():
    agent = RecordingAgent()

    service = ReportingService(
        agent,
        FakeConfig(),
    )

    report = service.generate_report(
        make_state("CONFLICTED")
    )

    assert report
    assert len(agent.prompts) == 1

    prompt = agent.prompts[0]

    assert (
        "DETERMINISTIC DECISION INTELLIGENCE CONTEXT"
        in prompt
    )
    assert (
        "Readiness status: CONFLICTED"
        in prompt
    )
    assert "PROVISIONAL_ONLY" in prompt
    assert (
        "Stopping reason: budget_exhausted"
        in prompt
    )
    assert (
        "Actionable research gaps: 4"
        in prompt
    )


def test_ready_report_prompt_allows_definitive_policy():
    agent = RecordingAgent()

    service = ReportingService(
        agent,
        FakeConfig(),
    )

    service.generate_report(
        make_state("READY")
    )

    prompt = agent.prompts[0]

    assert (
        "DEFINITIVE_RECOMMENDATION_ALLOWED"
        in prompt
    )
    assert "PROVISIONAL_ONLY" not in prompt


def test_non_decision_report_prompt_stays_legacy_compatible():
    agent = RecordingAgent()

    service = ReportingService(
        agent,
        FakeConfig(),
    )

    state = SummaryState(
        research_topic="Explain transformers",
        todo_items=[
            TodoItem(
                id=1,
                title="Attention",
                intent="Explain attention",
                query="transformer attention",
                status="completed",
                summary="Attention summary",
                sources_summary="Sources",
            )
        ],
    )

    service.generate_report(state)

    prompt = agent.prompts[0]

    assert (
        "DETERMINISTIC DECISION INTELLIGENCE CONTEXT"
        not in prompt
    )
    assert "PROVISIONAL_ONLY" not in prompt
    assert (
        "研究主题：Explain transformers"
        in prompt
    )
