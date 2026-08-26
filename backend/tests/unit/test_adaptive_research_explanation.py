from models import (
    AdaptiveResearchIteration,
    ResearchStoppingDecision,
)
from services.adaptive_research_explanation import (
    build_adaptive_research_explanation,
)


def iteration(
    *,
    value="LOW_VALUE",
):
    return AdaptiveResearchIteration(
        decision_id="dec_test",
        iteration_number=2,
        status="completed",
        retrieval_yield_status="LOW_YIELD",
        evidence_saturation_status="HIGH_SATURATION",
        information_gain_status="NO_INFORMATION_GAIN",
        adaptive_research_value_status=value,
        new_evidence_count=6,
        new_unique_source_count=5,
        novel_content_count=1,
        near_duplicate_content_ratio=0.67,
        duplicate_domain_ratio=0.83,
        novel_claim_count=1,
        claim_novelty_ratio=0.2,
        new_directional_signal_count=0,
        new_candidate_criterion_pairs=[],
    )


def stopping(
    *,
    should_continue=False,
    reason="diminishing_returns",
    low_count=2,
):
    return ResearchStoppingDecision(
        should_continue=should_continue,
        reason=reason,
        readiness_score=0.5,
        readiness_status="NOT_READY",
        consecutive_low_value_iterations=low_count,
    )


def test_low_value_summary_is_human_readable():
    item = iteration()

    build_adaptive_research_explanation(
        item,
        stopping(),
    )

    assert (
        item.research_value_summary
        == (
            "This research iteration added limited "
            "decision-relevant value."
        )
    )


def test_explanation_contains_phase_29_to_32_chain():
    item = iteration()

    build_adaptive_research_explanation(
        item,
        stopping(),
    )

    assert (
        "retrieval yield: low_yield"
        in item.research_value_explanation
    )

    assert (
        "evidence saturation: high_saturation"
        in item.research_value_explanation
    )

    assert (
        "decision information gain: no_information_gain"
        in item.research_value_explanation
    )

    assert (
        "adaptive research value: low_value"
        in item.research_value_explanation
    )


def test_observations_expose_quantitative_evidence():
    item = iteration()

    build_adaptive_research_explanation(
        item,
        stopping(),
    )

    assert (
        "6 new evidence item(s)"
        in item.research_value_observations
    )

    assert (
        "5 new unique source URL(s)"
        in item.research_value_observations
    )

    assert (
        "1 novel claim(s)"
        in item.research_value_observations
    )

    assert (
        "near-duplicate content ratio: 0.67"
        in item.research_value_observations
    )


def test_diminishing_returns_stop_is_explained():
    item = iteration()

    build_adaptive_research_explanation(
        item,
        stopping(
            low_count=2,
        ),
    )

    assert (
        "diminishing returns"
        in item.stopping_explanation
    )

    assert (
        "2 consecutive low-value iteration(s)"
        in item.stopping_explanation
    )


def test_existing_non_diminishing_stop_is_preserved_in_explanation():
    item = iteration(
        value="HIGH_VALUE",
    )

    build_adaptive_research_explanation(
        item,
        stopping(
            reason="decision_ready",
            low_count=0,
        ),
    )

    assert (
        item.stopping_explanation
        == (
            "Adaptive research stopped; "
            "reason: decision_ready."
        )
    )


def test_continue_state_is_explained():
    item = iteration(
        value="HIGH_VALUE",
    )

    build_adaptive_research_explanation(
        item,
        stopping(
            should_continue=True,
            reason="continue_research",
            low_count=0,
        ),
    )

    assert (
        item.stopping_explanation
        == (
            "Adaptive research continues; "
            "current stopping reason: continue_research."
        )
    )


def test_unknown_value_does_not_invent_explanation():
    item = iteration(
        value="UNKNOWN",
    )

    build_adaptive_research_explanation(
        item,
        None,
    )

    assert (
        "could not be determined"
        in item.research_value_summary
    )

    assert (
        item.stopping_explanation
        == (
            "No stopping decision was available "
            "after this iteration."
        )
    )


def test_builder_is_deterministic():
    first = iteration()
    second = iteration()

    build_adaptive_research_explanation(
        first,
        stopping(),
    )

    build_adaptive_research_explanation(
        second,
        stopping(),
    )

    assert (
        first.research_value_summary
        == second.research_value_summary
    )

    assert (
        first.research_value_explanation
        == second.research_value_explanation
    )

    assert (
        first.research_value_observations
        == second.research_value_observations
    )

    assert (
        first.stopping_explanation
        == second.stopping_explanation
    )


def test_explanation_fields_have_safe_defaults():
    item = AdaptiveResearchIteration(
        decision_id="legacy",
        iteration_number=1,
    )

    assert item.research_value_summary == ""
    assert item.research_value_explanation == []
    assert item.research_value_observations == []
    assert item.stopping_explanation == ""
