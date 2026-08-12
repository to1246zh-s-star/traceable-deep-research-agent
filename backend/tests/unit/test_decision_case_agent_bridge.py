from agent import DeepResearchAgent
from models import Candidate, DecisionCase


class StubExtractor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def extract(self, research_topic):
        self.calls.append(research_topic)
        return self.result


def test_agent_decision_case_bridge_returns_decision():
    agent = object.__new__(DeepResearchAgent)

    expected = DecisionCase(
        decision_id="dec_bridge",
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

    extractor = StubExtractor(expected)
    agent.decision_case_extractor = extractor

    result = agent.extract_decision_case(
        "Compare Qdrant and Milvus."
    )

    assert result is expected
    assert extractor.calls == [
        "Compare Qdrant and Milvus."
    ]


def test_agent_decision_case_bridge_returns_none():
    agent = object.__new__(DeepResearchAgent)

    extractor = StubExtractor(None)
    agent.decision_case_extractor = extractor

    result = agent.extract_decision_case(
        "Explain transformer attention."
    )

    assert result is None
    assert extractor.calls == [
        "Explain transformer attention."
    ]
