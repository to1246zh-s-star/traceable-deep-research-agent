from agent import DeepResearchAgent
from models import Candidate, DecisionCase, SummaryState


class StubExtractor:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def extract(self, topic):
        self.calls.append(topic)

        if self.error is not None:
            raise self.error

        return self.result


def make_agent(extractor):
    agent = object.__new__(DeepResearchAgent)
    agent.decision_case_extractor = extractor
    return agent


def test_attach_decision_case_updates_state():
    decision = DecisionCase(
        decision_id="dec_workflow",
        question="Qdrant or Milvus?",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            ),
            Candidate(
                candidate_id="cand_milvus",
                name="Milvus",
            ),
        ],
    )

    extractor = StubExtractor(result=decision)
    agent = make_agent(extractor)

    state = SummaryState(
        research_topic="Compare Qdrant and Milvus."
    )

    result = agent._attach_decision_case(state)

    assert result is decision
    assert state.decision_case is decision
    assert extractor.calls == [
        "Compare Qdrant and Milvus."
    ]


def test_attach_non_decision_keeps_state_empty():
    extractor = StubExtractor(result=None)
    agent = make_agent(extractor)

    state = SummaryState(
        research_topic="Explain transformer attention."
    )

    result = agent._attach_decision_case(state)

    assert result is None
    assert state.decision_case is None


def test_attach_extractor_failure_does_not_break_research():
    extractor = StubExtractor(
        error=RuntimeError("LLM unavailable")
    )
    agent = make_agent(extractor)

    state = SummaryState(
        research_topic="Compare Qdrant and Milvus."
    )

    result = agent._attach_decision_case(state)

    assert result is None
    assert state.decision_case is None
