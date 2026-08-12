from agent import DeepResearchAgent
from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    EvidenceSignal,
    SummaryState,
)


class StubSemanticExtractor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def extract(
        self,
        state,
        decision,
        proposals,
    ):
        self.calls.append(
            (state, decision, proposals)
        )
        return self.result


def make_decision():
    return DecisionCase(
        decision_id="dec_semantic_bridge",
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
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operations",
                weight=1.0,
            )
        ],
    )


def test_agent_semantic_signal_bridge():
    agent = object.__new__(
        DeepResearchAgent
    )

    state = SummaryState(
        research_topic="Choose A or B"
    )

    decision = make_decision()

    proposal = EvidenceSignal(
        signal_id="sig_proposal",
        evidence_id="evi_a",
        candidate_id="cand_a",
        criterion_id="crit_ops",
        direction="neutral",
        strength=0.5,
        source_confidence=0.9,
        applicability=0.8,
    )

    interpreted = EvidenceSignal(
        signal_id="sig_interpreted",
        evidence_id="evi_a",
        candidate_id="cand_a",
        criterion_id="crit_ops",
        direction="positive",
        strength=0.8,
        source_confidence=0.9,
        applicability=0.8,
    )

    extractor = StubSemanticExtractor(
        [interpreted]
    )

    agent.semantic_signal_extractor = (
        extractor
    )

    result = agent.extract_semantic_signals(
        state,
        decision,
        [proposal],
    )

    assert result == [interpreted]
    assert extractor.calls == [
        (
            state,
            decision,
            [proposal],
        )
    ]
