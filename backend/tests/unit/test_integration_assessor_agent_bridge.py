from agent import DeepResearchAgent
from models import (
    Candidate,
    DecisionCase,
    IntegrationAssessment,
    SummaryState,
    TechnicalContext,
)


def make_decision():
    return DecisionCase(
        decision_id="dec_bridge_arch",
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


class StubAssessor:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result or []
        self.error = error
        self.calls = []
        self.llm_call_count = 0

    def assess(
        self,
        state,
        decision,
        context,
    ):
        self.calls.append(
            (state, decision, context)
        )

        self.llm_call_count += 1

        if self.error is not None:
            raise self.error

        return self.result


def test_agent_integration_assessment_bridge():
    decision = make_decision()

    context = TechnicalContext(
        existing_stack=["Python"]
    )

    assessment = IntegrationAssessment(
        decision_id=decision.decision_id,
        candidate_id="cand_a",
        integration_complexity="LOW",
    )

    assessor = StubAssessor(
        [assessment]
    )

    agent = object.__new__(
        DeepResearchAgent
    )
    agent.integration_assessor = assessor

    state = SummaryState()

    result = agent.assess_integration(
        state,
        decision,
        context,
    )

    assert result == [assessment]

    assert assessor.calls == [
        (
            state,
            decision,
            context,
        )
    ]


def test_missing_assessor_is_safe():
    agent = object.__new__(
        DeepResearchAgent
    )

    result = agent.assess_integration(
        SummaryState(),
        make_decision(),
        TechnicalContext(
            existing_stack=["Python"]
        ),
    )

    assert result == []


def test_assessor_failure_is_safe():
    agent = object.__new__(
        DeepResearchAgent
    )

    agent.integration_assessor = (
        StubAssessor(
            error=RuntimeError(
                "architecture model failed"
            )
        )
    )

    result = agent.assess_integration(
        SummaryState(),
        make_decision(),
        TechnicalContext(
            existing_stack=["Python"]
        ),
    )

    assert result == []
