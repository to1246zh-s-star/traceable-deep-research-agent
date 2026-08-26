from models import (
    AdaptiveResearchIteration,
    ResearchStoppingDecision,
)
from services.adaptive_research_value import (
    apply_adaptive_research_value_stop,
    assess_iteration_research_value,
    consecutive_low_value_count,
)


def iteration(
    *,
    status="completed",
    retrieval="MODERATE_YIELD",
    saturation="LOW_SATURATION",
    information="MODERATE_INFORMATION_GAIN",
):
    return AdaptiveResearchIteration(
        decision_id="dec_test",
        iteration_number=1,
        status=status,
        retrieval_yield_status=retrieval,
        evidence_saturation_status=saturation,
        information_gain_status=information,
    )


def stopping(
    *,
    should_continue=True,
    reason="continue_research",
):
    return ResearchStoppingDecision(
        should_continue=should_continue,
        reason=reason,
        readiness_score=0.5,
        readiness_status="NOT_READY",
    )


def test_high_information_gain_is_high_value():
    item = iteration(
        retrieval="LOW_YIELD",
        saturation="HIGH_SATURATION",
        information="HIGH_INFORMATION_GAIN",
    )

    assert (
        assess_iteration_research_value(
            item
        )
        == "HIGH_VALUE"
    )


def test_moderate_information_gain_is_moderate_value():
    item = iteration(
        retrieval="LOW_YIELD",
        saturation="HIGH_SATURATION",
        information="MODERATE_INFORMATION_GAIN",
    )

    assert (
        assess_iteration_research_value(
            item
        )
        == "MODERATE_VALUE"
    )


def test_low_information_gain_is_low_value():
    item = iteration(
        retrieval="HIGH_YIELD",
        saturation="LOW_SATURATION",
        information="LOW_INFORMATION_GAIN",
    )

    assert (
        assess_iteration_research_value(
            item
        )
        == "LOW_VALUE"
    )


def test_no_information_but_diverse_retrieval_is_low_value():
    item = iteration(
        retrieval="HIGH_YIELD",
        saturation="LOW_SATURATION",
        information="NO_INFORMATION_GAIN",
    )

    assert (
        assess_iteration_research_value(
            item
        )
        == "LOW_VALUE"
    )


def test_no_information_and_low_retrieval_is_no_value():
    item = iteration(
        retrieval="LOW_YIELD",
        saturation="HIGH_SATURATION",
        information="NO_INFORMATION_GAIN",
    )

    assert (
        assess_iteration_research_value(
            item
        )
        == "NO_VALUE"
    )


def test_unknown_information_never_becomes_low_value():
    item = iteration(
        retrieval="NO_YIELD",
        saturation="UNKNOWN",
        information="UNKNOWN",
    )

    assert (
        assess_iteration_research_value(
            item
        )
        == "UNKNOWN"
    )


def test_failed_iteration_is_unknown():
    item = iteration(
        status="failed",
        information="NO_INFORMATION_GAIN",
    )

    assert (
        assess_iteration_research_value(
            item
        )
        == "UNKNOWN"
    )


def test_unknown_breaks_low_value_streak():
    first = iteration()
    first.adaptive_research_value_status = (
        "LOW_VALUE"
    )

    second = iteration()
    second.adaptive_research_value_status = (
        "UNKNOWN"
    )

    third = iteration()
    third.adaptive_research_value_status = (
        "NO_VALUE"
    )

    assert (
        consecutive_low_value_count(
            [
                first,
                second,
                third,
            ]
        )
        == 1
    )


def test_two_low_value_iterations_stop():
    first = iteration()
    first.adaptive_research_value_status = (
        "LOW_VALUE"
    )

    second = iteration()
    second.adaptive_research_value_status = (
        "NO_VALUE"
    )

    decision = (
        apply_adaptive_research_value_stop(
            stopping(),
            [
                first,
                second,
            ],
        )
    )

    assert decision is not None
    assert decision.should_continue is False

    # Preserve Phase29 public reason semantics.
    assert (
        decision.reason
        == "diminishing_returns"
    )

    assert (
        decision.consecutive_low_value_iterations
        == 2
    )


def test_useful_value_resets_streak():
    first = iteration()
    first.adaptive_research_value_status = (
        "LOW_VALUE"
    )

    second = iteration()
    second.adaptive_research_value_status = (
        "HIGH_VALUE"
    )

    third = iteration()
    third.adaptive_research_value_status = (
        "NO_VALUE"
    )

    assert (
        consecutive_low_value_count(
            [
                first,
                second,
                third,
            ]
        )
        == 1
    )


def test_existing_stop_reason_is_preserved():
    first = iteration()
    first.adaptive_research_value_status = (
        "LOW_VALUE"
    )

    second = iteration()
    second.adaptive_research_value_status = (
        "NO_VALUE"
    )

    decision = (
        apply_adaptive_research_value_stop(
            stopping(
                should_continue=False,
                reason="decision_ready",
            ),
            [
                first,
                second,
            ],
        )
    )

    assert decision.reason == "decision_ready"


def test_value_assessment_is_deterministic():
    first = iteration(
        retrieval="MODERATE_YIELD",
        saturation="MODERATE_SATURATION",
        information="MODERATE_INFORMATION_GAIN",
    )

    second = iteration(
        retrieval="MODERATE_YIELD",
        saturation="MODERATE_SATURATION",
        information="MODERATE_INFORMATION_GAIN",
    )

    assert (
        assess_iteration_research_value(first)
        == assess_iteration_research_value(second)
    )

    assert (
        first.adaptive_research_value_reasons
        == second.adaptive_research_value_reasons
    )


def test_high_information_gain_prevents_low_value_stop():
    first = iteration(
        retrieval="NO_YIELD",
        saturation="UNKNOWN",
        information="HIGH_INFORMATION_GAIN",
    )

    second = iteration(
        retrieval="NO_YIELD",
        saturation="UNKNOWN",
        information="HIGH_INFORMATION_GAIN",
    )

    assess_iteration_research_value(
        first
    )
    assess_iteration_research_value(
        second
    )

    decision = (
        apply_adaptive_research_value_stop(
            stopping(),
            [
                first,
                second,
            ],
        )
    )

    assert (
        first.adaptive_research_value_status
        == "HIGH_VALUE"
    )

    assert (
        second.adaptive_research_value_status
        == "HIGH_VALUE"
    )

    assert decision.should_continue is True
    assert (
        decision.consecutive_low_value_iterations
        == 0
    )
