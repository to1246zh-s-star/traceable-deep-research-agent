import pytest

from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    EvidenceSignal,
    SummaryState,
)
from services.decision_input_builder import (
    build_candidate_criterion_scores,
)
from services.decision_pipeline import run_decision_pipeline


def make_decision():
    return DecisionCase(
        decision_id="dec_score_builder",
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


def signal(
    evidence_id,
    candidate_id,
    direction,
    *,
    strength=1.0,
    confidence=1.0,
    applicability=1.0,
):
    return EvidenceSignal(
        evidence_id=evidence_id,
        candidate_id=candidate_id,
        criterion_id="crit_ops",
        direction=direction,
        strength=strength,
        source_confidence=confidence,
        applicability=applicability,
    )


def test_positive_signal_produces_high_score():
    decision = make_decision()

    scores = build_candidate_criterion_scores(
        decision,
        [
            signal(
                "evi_positive",
                "cand_a",
                "positive",
                strength=0.8,
            )
        ],
    )

    assert len(scores) == 1
    assert scores[0].candidate_id == "cand_a"
    assert scores[0].fitness_score == pytest.approx(9.0)


def test_negative_signal_produces_low_score():
    decision = make_decision()

    scores = build_candidate_criterion_scores(
        decision,
        [
            signal(
                "evi_negative",
                "cand_a",
                "negative",
                strength=0.8,
            )
        ],
    )

    assert len(scores) == 1
    assert scores[0].fitness_score == pytest.approx(1.0)


def test_conflicting_signals_move_score_toward_neutral():
    decision = make_decision()

    scores = build_candidate_criterion_scores(
        decision,
        [
            signal(
                "evi_positive",
                "cand_a",
                "positive",
                strength=0.8,
            ),
            signal(
                "evi_negative",
                "cand_a",
                "negative",
                strength=0.8,
            ),
        ],
    )

    assert len(scores) == 1
    assert scores[0].fitness_score == pytest.approx(5.0)


def test_neutral_only_signal_does_not_invent_score():
    decision = make_decision()

    scores = build_candidate_criterion_scores(
        decision,
        [
            signal(
                "evi_neutral",
                "cand_a",
                "neutral",
            )
        ],
    )

    assert scores == []


def test_missing_candidate_pair_is_omitted():
    decision = make_decision()

    scores = build_candidate_criterion_scores(
        decision,
        [
            signal(
                "evi_a",
                "cand_a",
                "positive",
                strength=0.6,
            )
        ],
    )

    assert len(scores) == 1
    assert scores[0].candidate_id == "cand_a"


def test_pipeline_auto_scores_directional_signals():
    decision = make_decision()

    state = SummaryState(
        research_topic="Choose A or B"
    )

    result = run_decision_pipeline(
        state,
        decision,
        evidence_signals=[
            signal(
                "evi_a",
                "cand_a",
                "positive",
                strength=0.8,
            ),
            signal(
                "evi_b",
                "cand_b",
                "positive",
                strength=0.4,
            ),
        ],
    )

    assert result is state
    assert state.decision_comparison is not None
    assert state.decision_comparison.status == "complete"

    ranked = state.decision_comparison.ranked_candidate_ids

    assert ranked == [
        "cand_a",
        "cand_b",
    ]


def test_pipeline_neutral_signals_remain_incomplete():
    decision = make_decision()

    state = SummaryState(
        research_topic="Choose A or B"
    )

    result = run_decision_pipeline(
        state,
        decision,
        evidence_signals=[
            signal(
                "evi_a",
                "cand_a",
                "neutral",
            ),
            signal(
                "evi_b",
                "cand_b",
                "neutral",
            ),
        ],
    )

    assert result is state
    assert state.decision_comparison is not None
    assert state.decision_comparison.status == "incomplete"
