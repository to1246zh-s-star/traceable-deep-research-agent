import pytest

from models import (
    Candidate,
    CandidateCriterionScore,
    CandidateWeightedScore,
    DecisionCase,
    DecisionComparison,
    DecisionCriterion,
)
from services.decision_sensitivity import analyze_decision_sensitivity


def make_two_candidate_decision():
    decision = DecisionCase(
        decision_id="dec_sensitivity",
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
                weight=0.7,
            ),
            DecisionCriterion(
                criterion_id="crit_scale",
                name="Scalability",
                weight=0.3,
            ),
        ],
    )

    scores = [
        CandidateCriterionScore(
            candidate_id="cand_a",
            criterion_id="crit_ops",
            fitness_score=9.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_a",
            criterion_id="crit_scale",
            fitness_score=5.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_b",
            criterion_id="crit_ops",
            fitness_score=6.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_b",
            criterion_id="crit_scale",
            fitness_score=10.0,
        ),
    ]

    # A = 7.8
    # B = 7.2
    comparison = DecisionComparison(
        decision_id=decision.decision_id,
        status="complete",
        candidate_scores=[
            CandidateWeightedScore(
                candidate_id="cand_a",
                weighted_score=7.8,
                rank=1,
            ),
            CandidateWeightedScore(
                candidate_id="cand_b",
                weighted_score=7.2,
                rank=2,
            ),
        ],
        ranked_candidate_ids=[
            "cand_a",
            "cand_b",
        ],
    )

    return decision, comparison, scores


def test_sensitivity_detects_weight_increase_flip():
    decision, comparison, scores = make_two_candidate_decision()

    results = analyze_decision_sensitivity(
        decision,
        comparison,
        scores,
        weight_step=0.01,
    )

    scalability = next(
        result
        for result in results
        if result.criterion_id == "crit_scale"
    )

    assert scalability.baseline_winner_id == "cand_a"
    assert scalability.baseline_weight == pytest.approx(0.3)

    assert scalability.recommendation_changes is True
    assert scalability.direction_of_change == "increase"
    assert scalability.competing_candidate_id == "cand_b"

    # Solve:
    # A = 9(1-w) + 5w = 9 - 4w
    # B = 6(1-w) + 10w = 6 + 4w
    # tie at w = 0.375, first strict grid flip = 0.38
    assert scalability.switch_threshold == pytest.approx(
        0.38,
        abs=1e-9,
    )
    assert scalability.weight_delta == pytest.approx(
        0.08,
        abs=1e-9,
    )

    assert scalability.score_margin_before == pytest.approx(0.6)
    assert scalability.score_margin_after < 0


def test_sensitivity_detects_equivalent_decrease_flip():
    decision, comparison, scores = make_two_candidate_decision()

    results = analyze_decision_sensitivity(
        decision,
        comparison,
        scores,
        weight_step=0.01,
    )

    operations = next(
        result
        for result in results
        if result.criterion_id == "crit_ops"
    )

    assert operations.recommendation_changes is True
    assert operations.direction_of_change == "decrease"
    assert operations.competing_candidate_id == "cand_b"

    # ops and scalability are complementary for this two-criterion case.
    assert operations.switch_threshold == pytest.approx(
        0.62,
        abs=1e-9,
    )


def test_incomplete_comparison_produces_no_sensitivity():
    decision, _, scores = make_two_candidate_decision()

    comparison = DecisionComparison(
        decision_id=decision.decision_id,
        status="incomplete",
    )

    assert (
        analyze_decision_sensitivity(
            decision,
            comparison,
            scores,
        )
        == []
    )


def test_single_ranked_candidate_produces_no_sensitivity():
    decision, comparison, scores = make_two_candidate_decision()

    comparison.ranked_candidate_ids = ["cand_a"]
    comparison.candidate_scores = [
        CandidateWeightedScore(
            candidate_id="cand_a",
            weighted_score=7.8,
            rank=1,
        )
    ]

    assert (
        analyze_decision_sensitivity(
            decision,
            comparison,
            scores,
        )
        == []
    )


def test_missing_candidate_criterion_score_produces_no_sensitivity():
    decision, comparison, scores = make_two_candidate_decision()

    incomplete_scores = [
        score
        for score in scores
        if not (
            score.candidate_id == "cand_b"
            and score.criterion_id == "crit_scale"
        )
    ]

    assert (
        analyze_decision_sensitivity(
            decision,
            comparison,
            incomplete_scores,
        )
        == []
    )


def test_tied_baseline_produces_no_sensitivity():
    decision, comparison, scores = make_two_candidate_decision()

    comparison.candidate_scores = [
        CandidateWeightedScore(
            candidate_id="cand_a",
            weighted_score=7.5,
            rank=1,
        ),
        CandidateWeightedScore(
            candidate_id="cand_b",
            weighted_score=7.5,
            rank=2,
        ),
    ]

    assert (
        analyze_decision_sensitivity(
            decision,
            comparison,
            scores,
        )
        == []
    )


def test_invalid_weight_step_is_rejected():
    decision, comparison, scores = make_two_candidate_decision()

    with pytest.raises(
        ValueError,
        match="weight_step must be positive",
    ):
        analyze_decision_sensitivity(
            decision,
            comparison,
            scores,
            weight_step=0,
        )


def test_no_flip_uses_explicit_empty_threshold_semantics():
    decision = DecisionCase(
        decision_id="dec_no_flip",
        question="Choose A or B",
        candidates=[
            Candidate(candidate_id="cand_a", name="A"),
            Candidate(candidate_id="cand_b", name="B"),
        ],
        criteria=[
            DecisionCriterion(
                criterion_id="crit_one",
                name="Only criterion",
                weight=1.0,
            )
        ],
    )

    scores = [
        CandidateCriterionScore(
            candidate_id="cand_a",
            criterion_id="crit_one",
            fitness_score=9.0,
        ),
        CandidateCriterionScore(
            candidate_id="cand_b",
            criterion_id="crit_one",
            fitness_score=5.0,
        ),
    ]

    comparison = DecisionComparison(
        decision_id=decision.decision_id,
        status="complete",
        candidate_scores=[
            CandidateWeightedScore(
                candidate_id="cand_a",
                weighted_score=9.0,
                rank=1,
            ),
            CandidateWeightedScore(
                candidate_id="cand_b",
                weighted_score=5.0,
                rank=2,
            ),
        ],
        ranked_candidate_ids=["cand_a", "cand_b"],
    )

    results = analyze_decision_sensitivity(
        decision,
        comparison,
        scores,
    )

    assert len(results) == 1

    result = results[0]

    assert result.recommendation_changes is False
    assert result.switch_threshold is None
    assert result.weight_delta is None
    assert result.direction_of_change is None
    assert result.competing_candidate_id is None
    assert result.score_margin_after is None
