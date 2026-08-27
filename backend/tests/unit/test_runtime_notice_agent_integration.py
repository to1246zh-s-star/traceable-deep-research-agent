from agent import DeepResearchAgent
from models import (
    Candidate,
    DecisionCase,
    SummaryState,
)


def make_agent():
    return object.__new__(
        DeepResearchAgent
    )


def make_decision():
    return DecisionCase(
        decision_id="dec_notice",
        question="A or B",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            )
        ],
    )


def test_integration_failure_records_notice():
    agent = make_agent()

    class FailingAssessor:
        def assess(
            self,
            state,
            decision,
            technical_context,
        ):
            raise RuntimeError(
                "Error code: 429 - insufficient balance"
            )

    agent.integration_assessor = (
        FailingAssessor()
    )

    state = SummaryState(
        research_topic="A vs B",
    )

    result = agent.assess_integration(
        state,
        make_decision(),
        None,
    )

    assert result == []

    assert len(
        state.runtime_notices
    ) == 1

    notice = state.runtime_notices[0]

    assert notice["stage"] == (
        "integration_assessment"
    )

    assert notice["error_type"] == (
        "quota_exceeded"
    )

    assert notice["degraded"] is True
