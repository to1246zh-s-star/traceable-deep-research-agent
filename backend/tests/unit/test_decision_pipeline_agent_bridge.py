from agent import DeepResearchAgent
from models import (
    Candidate,
    CandidateCriterionScore,
    DecisionCase,
    DecisionCriterion,
    EvidenceSignal,
    SummaryState,
)


def test_agent_executes_decision_pipeline_bridge():
    agent = object.__new__(DeepResearchAgent)

    state = SummaryState(
        research_topic="Qdrant vs Milvus"
    )

    decision = DecisionCase(
        decision_id="dec_agent_bridge",
        question="Which vector database should we choose?",
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
                source="user",
            )
        ],
    )

    criterion_scores = [
        CandidateCriterionScore(
            candidate_id="cand_qdrant",
            criterion_id="crit_ops",
            fitness_score=8.0,
            rationale="Simpler operations",
        ),
        CandidateCriterionScore(
            candidate_id="cand_milvus",
            criterion_id="crit_ops",
            fitness_score=6.0,
            rationale="More operational components",
        ),
    ]

    signals = [
        EvidenceSignal(
            evidence_id="evi_qdrant",
            candidate_id="cand_qdrant",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.9,
            source_confidence=0.9,
            applicability=0.9,
        ),
        EvidenceSignal(
            evidence_id="evi_milvus",
            candidate_id="cand_milvus",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.8,
            source_confidence=0.8,
            applicability=0.8,
        ),
    ]

    result = agent.execute_decision_pipeline(
        state,
        decision,
        criterion_scores=criterion_scores,
        evidence_signals=signals,
    )

    assert result is state

    assert state.decision_case is decision
    assert state.decision_evaluation is not None
    assert state.decision_comparison is not None
    assert state.research_analysis is not None
    assert state.decision_readiness is not None
    assert state.stopping_decision is not None

    assert state.decision_comparison.ranked_candidate_ids[0] == (
        "cand_qdrant"
    )


def test_agent_bridge_preserves_existing_research_state():
    agent = object.__new__(DeepResearchAgent)

    state = SummaryState(
        research_topic="Database decision",
        running_summary="Existing research summary",
    )

    decision = DecisionCase(
        decision_id="dec_preserve",
        question="Choose a database",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            )
        ],
    )

    agent.execute_decision_pipeline(
        state,
        decision,
    )

    assert state.research_topic == "Database decision"
    assert state.running_summary == "Existing research summary"
    assert state.decision_case is decision
