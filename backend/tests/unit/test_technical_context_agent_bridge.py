from agent import DeepResearchAgent
from models import (
    Candidate,
    DecisionCase,
    SummaryState,
    TechnicalContext,
)


class StubContextExtractor:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []
        self.llm_call_count = 0

    def extract(self, topic, decision):
        self.calls.append((topic, decision))
        self.llm_call_count += 1

        if self.error is not None:
            raise self.error

        return self.result


def make_decision():
    return DecisionCase(
        decision_id="dec_context_bridge",
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


def test_agent_extracts_technical_context():
    context = TechnicalContext(
        existing_stack=["Python"]
    )

    extractor = StubContextExtractor(
        result=context
    )

    agent = object.__new__(DeepResearchAgent)
    agent.technical_context_extractor = extractor

    state = SummaryState(
        research_topic="Choose A or B"
    )

    decision = make_decision()

    result = agent.extract_technical_context(
        state,
        decision,
    )

    assert result is context
    assert extractor.calls == [
        ("Choose A or B", decision)
    ]


def test_agent_reuses_existing_context():
    context = TechnicalContext(
        existing_stack=["Python"]
    )

    extractor = StubContextExtractor()

    agent = object.__new__(DeepResearchAgent)
    agent.technical_context_extractor = extractor

    state = SummaryState(
        research_topic="Choose A or B",
        technical_context=context,
    )

    result = agent.extract_technical_context(
        state,
        make_decision(),
    )

    assert result is context
    assert extractor.calls == []


def test_context_failure_is_safe():
    extractor = StubContextExtractor(
        error=RuntimeError(
            "context model unavailable"
        )
    )

    agent = object.__new__(DeepResearchAgent)
    agent.technical_context_extractor = extractor

    state = SummaryState(
        research_topic="Choose A or B"
    )

    result = agent.extract_technical_context(
        state,
        make_decision(),
    )

    assert result is None
    assert state.technical_context is None


def test_missing_context_extractor_is_safe():
    agent = object.__new__(DeepResearchAgent)

    state = SummaryState(
        research_topic="Choose A or B"
    )

    result = agent.extract_technical_context(
        state,
        make_decision(),
    )

    assert result is None
