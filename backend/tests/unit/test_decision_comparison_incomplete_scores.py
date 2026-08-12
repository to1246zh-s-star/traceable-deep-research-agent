import pytest

from models import (
    Candidate,
    CandidateCriterionScore,
    DecisionCase,
    DecisionCriterion,
    SummaryState,
)
from services.decision_comparison import compare_candidates
from services.decision_evaluator import evaluate_decision_case
from services.decision_pipeline import run_decision_pipeline


def make_decision():
    return DecisionCase(
        decision_id="dec_missing_scores",
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


def test_low_level_comparison_stays_strict():
    decision = make_decision()
    evaluation = evaluate_decision_case(decision)

    with pytest.raises(
        ValueError,
        match="missing score",
    ):
        compare_candidates(
            decision,
            evaluation,
            [
                CandidateCriterionScore(
                    candidate_id="cand_a",
                    criterion_id="crit_ops",
                    fitness_score=8.0,
                )
            ],
        )


def test_pipeline_degrades_missing_scores_to_incomplete():
    decision = make_decision()

    state = SummaryState(
        research_topic="Choose A or B"
    )

    result = run_decision_pipeline(
        state,
        decision,
        criterion_scores=[
            CandidateCriterionScore(
                candidate_id="cand_a",
                criterion_id="crit_ops",
                fitness_score=8.0,
            )
        ],
    )

    assert result is state
    assert state.decision_comparison is not None
    assert state.decision_comparison.status == "incomplete"
    assert state.decision_comparison.ranked_candidate_ids == []


def test_pipeline_does_not_hide_invalid_scores():
    decision = make_decision()

    state = SummaryState(
        research_topic="Choose A or B"
    )

    with pytest.raises(
        ValueError,
        match="fitness score",
    ):
        run_decision_pipeline(
            state,
            decision,
            criterion_scores=[
                CandidateCriterionScore(
                    candidate_id="cand_a",
                    criterion_id="crit_ops",
                    fitness_score=99.0,
                ),
                CandidateCriterionScore(
                    candidate_id="cand_b",
                    criterion_id="crit_ops",
                    fitness_score=5.0,
                ),
            ],
        )
