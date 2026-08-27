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

    integration_notices = [
        notice
        for notice in state.runtime_notices
        if notice["stage"]
        == "integration_assessment"
    ]

    assert len(integration_notices) == 1

    notice = integration_notices[0]

    assert notice["error_type"] == (
        "quota_exceeded"
    )

    assert notice["degraded"] is True

    circuit_notices = [
        notice
        for notice in state.runtime_notices
        if notice["stage"]
        == "llm_runtime_circuit"
    ]

    assert len(circuit_notices) == 1

    circuit_notice = circuit_notices[0]

    assert circuit_notice["error_type"] == (
        "quota_exceeded"
    )

    assert circuit_notice["metadata"][
        "status"
    ] == "open"

    assert circuit_notice["metadata"][
        "trigger_stage"
    ] == "integration_assessment"

    assert (
        state.llm_runtime_circuit["status"]
        == "open"
    )

    assert (
        state.llm_runtime_circuit[
            "error_type"
        ]
        == "quota_exceeded"
    )
