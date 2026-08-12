from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    Evidence,
    EvidenceSignal,
    SummaryState,
)
from services.semantic_signal_extractor import (
    SemanticSignalExtractor,
)


class DummyConfig:
    strip_thinking_tokens = False


class StubAgent:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)

        response = self.responses[
            self.calls
        ]

        self.calls += 1
        return response

    def clear_history(self):
        pass


def make_inputs():
    decision = DecisionCase(
        decision_id="dec_semantic",
        question="Choose Qdrant or Milvus",
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
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operational simplicity",
                weight=1.0,
            )
        ],
    )

    state = SummaryState(
        research_topic="Qdrant vs Milvus",
        evidence_items=[
            Evidence(
                evidence_id="evi_qdrant",
                task_id=1,
                trace_id="trace_1",
                query="Qdrant operations",
                backend="web",
                source_title="Qdrant documentation",
                snippet=(
                    "Qdrant can be deployed as a "
                    "single self-contained service."
                ),
            )
        ],
    )

    proposal = EvidenceSignal(
        signal_id="sig_proposal",
        evidence_id="evi_qdrant",
        candidate_id="cand_qdrant",
        criterion_id="crit_ops",
        direction="neutral",
        strength=0.5,
        source_confidence=0.9,
        applicability=0.8,
    )

    return state, decision, proposal


def test_semantic_signal_positive():
    state, decision, proposal = (
        make_inputs()
    )

    agent = StubAgent([
        """
        {
          "direction": "positive",
          "strength": 0.8,
          "rationale": "Simpler deployment."
        }
        """
    ])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal],
    )

    assert len(signals) == 1

    signal = signals[0]

    assert signal.direction == "positive"
    assert signal.strength == 0.8

    # Deterministic quality metadata is preserved.
    assert signal.source_confidence == 0.9
    assert signal.applicability == 0.8


def test_semantic_signal_negative():
    state, decision, proposal = (
        make_inputs()
    )

    agent = StubAgent([
        """
        {
          "direction": "negative",
          "strength": 0.7,
          "rationale": "Operational burden."
        }
        """
    ])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal],
    )

    assert signals[0].direction == "negative"
    assert signals[0].strength == 0.7


def test_ambiguous_evidence_can_remain_neutral():
    state, decision, proposal = (
        make_inputs()
    )

    agent = StubAgent([
        """
        {
          "direction": "neutral",
          "strength": 0.2,
          "rationale": "No clear advantage."
        }
        """
    ])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal],
    )

    assert signals[0].direction == "neutral"
    assert signals[0].strength == 0.2


def test_invalid_json_retries_once():
    state, decision, proposal = (
        make_inputs()
    )

    agent = StubAgent([
        '{"direction":',
        """
        {
          "direction": "positive",
          "strength": 0.6,
          "rationale": "Recovered."
        }
        """,
    ])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal],
    )

    assert agent.calls == 2
    assert signals[0].direction == "positive"
    assert signals[0].strength == 0.6


def test_repeated_failure_preserves_neutral_proposal():
    state, decision, proposal = (
        make_inputs()
    )

    agent = StubAgent([
        '{"direction":',
        '{"direction":',
    ])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal],
    )

    assert agent.calls == 2

    # Fail closed: never invent semantic direction.
    assert signals[0] is proposal
    assert signals[0].direction == "neutral"


def test_missing_evidence_skips_invalid_proposal():
    state, decision, proposal = (
        make_inputs()
    )

    proposal.evidence_id = "missing"

    agent = StubAgent([])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal],
    )

    assert signals == []
    assert agent.calls == 0
