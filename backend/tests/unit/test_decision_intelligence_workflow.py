from agent import DeepResearchAgent
from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    Evidence,
    EvidenceSignal,
    SummaryState,
)


class StubSemanticExtractor:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
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

        if self.error is not None:
            raise self.error

        return (
            self.result
            if self.result is not None
            else proposals
        )


def make_decision():
    return DecisionCase(
        decision_id="dec_full_workflow",
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


def make_state():
    return SummaryState(
        research_topic="Qdrant vs Milvus",
        decision_case=make_decision(),
        evidence_items=[
            Evidence(
                evidence_id="evi_qdrant",
                task_id=1,
                trace_id="trace_1",
                query="Qdrant operational simplicity",
                backend="web",
                source_title="Qdrant documentation",
                snippet=(
                    "Qdrant operational simplicity "
                    "and deployment."
                ),
                source_rank=1,
            ),
            Evidence(
                evidence_id="evi_milvus",
                task_id=2,
                trace_id="trace_2",
                query="Milvus operational simplicity",
                backend="web",
                source_title="Milvus documentation",
                snippet=(
                    "Milvus operational simplicity "
                    "and deployment."
                ),
                source_rank=1,
            ),
        ],
    )


def make_agent(extractor):
    agent = object.__new__(
        DeepResearchAgent
    )
    agent.semantic_signal_extractor = extractor
    return agent


def test_no_decision_case_is_noop():
    state = SummaryState(
        research_topic="Explain attention"
    )

    extractor = StubSemanticExtractor()
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state
    assert extractor.calls == []
    assert state.decision_evaluation is None


def test_full_workflow_uses_semantic_signals():
    state = make_state()

    semantic_signals = [
        EvidenceSignal(
            evidence_id="evi_qdrant",
            candidate_id="cand_qdrant",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.8,
            source_confidence=0.9,
            applicability=0.9,
        ),
        EvidenceSignal(
            evidence_id="evi_milvus",
            candidate_id="cand_milvus",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.4,
            source_confidence=0.9,
            applicability=0.9,
        ),
    ]

    extractor = StubSemanticExtractor(
        result=semantic_signals
    )
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state

    assert len(
        state.evidence_assessments
    ) == 2

    assert state.evidence_signals == (
        semantic_signals
    )

    assert state.decision_evaluation is not None
    assert state.decision_comparison is not None

    assert (
        state.decision_comparison.status
        == "complete"
    )

    assert (
        state.decision_comparison
        .ranked_candidate_ids
        == [
            "cand_qdrant",
            "cand_milvus",
        ]
    )

    assert state.research_analysis is not None
    assert state.decision_readiness is not None
    assert state.stopping_decision is not None


def test_semantic_failure_falls_back_to_neutral():
    state = make_state()

    extractor = StubSemanticExtractor(
        error=RuntimeError(
            "semantic model unavailable"
        )
    )
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state

    assert state.evidence_signals
    assert all(
        signal.direction == "neutral"
        for signal in state.evidence_signals
    )

    assert state.decision_comparison is not None
    assert (
        state.decision_comparison.status
        == "incomplete"
    )


def test_constraints_remain_unresolved_without_results():
    state = make_state()

    from models import Constraint

    state.decision_case.constraints = [
        Constraint(
            constraint_id="con_self_hosted",
            text="Must support self-hosting",
        )
    ]

    extractor = StubSemanticExtractor()
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state

    assert state.decision_evaluation is not None
    assert (
        state.decision_evaluation.status
        == "incomplete"
    )

    assert set(
        state.decision_evaluation
        .unresolved_candidate_ids
    ) == {
        "cand_qdrant",
        "cand_milvus",
    }

    assert (
        state.decision_comparison.status
        == "incomplete"
    )
