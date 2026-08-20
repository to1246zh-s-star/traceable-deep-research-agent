from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    Evidence,
    EvidenceSignal,
    SummaryState,
)
from services.semantic_signal_extractor import SemanticSignalExtractor


class DummyConfig:
    strip_thinking_tokens = False


class StubAgent:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)

        response = self.responses[self.calls]
        self.calls += 1

        return response

    def clear_history(self):
        pass


def make_inputs():
    decision = DecisionCase(
        decision_id="dec_test",
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
            ),
        ],
    )

    evidence = Evidence(
        evidence_id="evi_qdrant",
        task_id=1,
        trace_id="trace_1",
        query="Qdrant operations",
        backend="web",
        source_title="Qdrant documentation",
        snippet="Qdrant can be deployed with a simple container setup.",
    )

    state = SummaryState(
        research_topic="Qdrant vs Milvus",
        evidence_items=[evidence],
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


def batch_response(
    *,
    signal_id="sig_proposal",
    direction="positive",
    strength=0.8,
    rationale="Evidence-grounded result.",
):
    return f"""
    {{
      "results": [
        {{
          "signal_id": "{signal_id}",
          "direction": "{direction}",
          "strength": {strength},
          "rationale": "{rationale}"
        }}
      ]
    }}
    """


def test_semantic_signal_positive():
    state, decision, proposal = make_inputs()

    agent = StubAgent([
        batch_response(
            direction="positive",
            strength=0.8,
            rationale="Simpler deployment.",
        )
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
    assert signal.rationale == "Simpler deployment."

    # Deterministic weights must remain untouched.
    assert signal.source_confidence == 0.9
    assert signal.applicability == 0.8

    assert agent.calls == 1


def test_semantic_signal_negative():
    state, decision, proposal = make_inputs()

    agent = StubAgent([
        batch_response(
            direction="negative",
            strength=0.7,
            rationale="Operational burden.",
        )
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
    assert agent.calls == 1


def test_ambiguous_evidence_can_remain_neutral():
    state, decision, proposal = make_inputs()

    agent = StubAgent([
        batch_response(
            direction="neutral",
            strength=0.2,
            rationale="No clear advantage.",
        )
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
    assert agent.calls == 1


def test_invalid_json_retries_once():
    state, decision, proposal = make_inputs()

    agent = StubAgent([
        '{"results":',
        batch_response(
            direction="positive",
            strength=0.6,
            rationale="Recovered.",
        ),
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


def test_repeated_failure_preserves_original_neutral_proposal():
    state, decision, proposal = make_inputs()

    agent = StubAgent([
        '{"results":',
        '{"results":',
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

    assert signals == [proposal]
    assert signals[0].direction == "neutral"
    assert signals[0].strength == 0.5


def test_missing_evidence_skips_invalid_proposal():
    state, decision, proposal = make_inputs()

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


def test_same_evidence_multiple_targets_use_one_llm_call():
    state, decision, proposal = make_inputs()

    decision.criteria.append(
        DecisionCriterion(
            criterion_id="crit_perf",
            name="Retrieval performance",
            weight=1.0,
        )
    )

    proposal2 = EvidenceSignal(
        signal_id="sig_perf",
        evidence_id=proposal.evidence_id,
        candidate_id=proposal.candidate_id,
        criterion_id="crit_perf",
        direction="neutral",
        strength=0.4,
        source_confidence=0.85,
        applicability=0.75,
    )

    agent = StubAgent([
        """
        {
          "results": [
            {
              "signal_id": "sig_proposal",
              "direction": "positive",
              "strength": 0.8,
              "rationale": "Simple deployment."
            },
            {
              "signal_id": "sig_perf",
              "direction": "neutral",
              "strength": 0.2,
              "rationale": "No benchmark evidence."
            }
          ]
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
        [proposal, proposal2],
    )

    assert agent.calls == 1
    assert len(signals) == 2

    assert signals[0].signal_id == "sig_proposal"
    assert signals[0].direction == "positive"

    assert signals[1].signal_id == "sig_perf"
    assert signals[1].direction == "neutral"

    assert signals[1].source_confidence == 0.85
    assert signals[1].applicability == 0.75


def test_different_evidence_items_use_separate_llm_calls():
    state, decision, proposal = make_inputs()

    state.evidence_items.append(
        Evidence(
            evidence_id="evi_second",
            task_id=2,
            trace_id="trace_2",
            query="Qdrant performance",
            backend="web",
            source_title="Benchmark",
            snippet="Qdrant benchmark results.",
        )
    )

    proposal2 = EvidenceSignal(
        signal_id="sig_second",
        evidence_id="evi_second",
        candidate_id="cand_qdrant",
        criterion_id="crit_ops",
        direction="neutral",
        strength=0.4,
        source_confidence=0.8,
        applicability=0.7,
    )

    agent = StubAgent([
        batch_response(
            signal_id="sig_proposal",
            direction="positive",
        ),
        batch_response(
            signal_id="sig_second",
            direction="negative",
        ),
    ])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal, proposal2],
    )

    assert agent.calls == 2
    assert signals[0].direction == "positive"
    assert signals[1].direction == "negative"


def test_missing_batch_result_preserves_that_proposal_neutral():
    state, decision, proposal = make_inputs()

    decision.criteria.append(
        DecisionCriterion(
            criterion_id="crit_perf",
            name="Retrieval performance",
            weight=1.0,
        )
    )

    proposal2 = EvidenceSignal(
        signal_id="sig_perf",
        evidence_id=proposal.evidence_id,
        candidate_id=proposal.candidate_id,
        criterion_id="crit_perf",
        direction="neutral",
        strength=0.3,
        source_confidence=0.8,
        applicability=0.7,
    )

    agent = StubAgent([
        batch_response(
            signal_id="sig_proposal",
            direction="positive",
            strength=0.9,
        )
    ])

    extractor = SemanticSignalExtractor(
        agent,
        DummyConfig(),
    )

    signals = extractor.extract(
        state,
        decision,
        [proposal, proposal2],
    )

    assert agent.calls == 1

    assert signals[0].direction == "positive"

    # Model omitted sig_perf -> fail closed for only that target.
    assert signals[1] is proposal2
    assert signals[1].direction == "neutral"
    assert signals[1].strength == 0.3


def test_invented_signal_id_retries_then_fails_closed():
    state, decision, proposal = make_inputs()

    agent = StubAgent([
        """
        {
          "results": [
            {
              "signal_id": "invented",
              "direction": "positive",
              "strength": 1.0,
              "rationale": "Invented."
            }
          ]
        }
        """,
        """
        {
          "results": [
            {
              "signal_id": "invented_again",
              "direction": "negative",
              "strength": 1.0,
              "rationale": "Still invented."
            }
          ]
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
    assert signals == [proposal]


def test_duplicate_signal_ids_are_rejected():
    state, decision, proposal = make_inputs()

    agent = StubAgent([
        """
        {
          "results": [
            {
              "signal_id": "sig_proposal",
              "direction": "positive",
              "strength": 0.8,
              "rationale": "First."
            },
            {
              "signal_id": "sig_proposal",
              "direction": "negative",
              "strength": 0.8,
              "rationale": "Duplicate."
            }
          ]
        }
        """,
        """
        {
          "results": []
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

    # Empty repaired batch means missing result -> preserve neutral.
    assert signals == [proposal]
