"""Unified deterministic value assessment for adaptive research."""

from __future__ import annotations

from models import (
    AdaptiveResearchIteration,
    ResearchStoppingDecision,
)


LOW_VALUE_STATUSES = {
    "LOW_VALUE",
    "NO_VALUE",
}


def assess_iteration_research_value(
    iteration: AdaptiveResearchIteration,
) -> str:
    """
    Combine retrieval yield, evidence saturation, and decision information gain.

    Decision-relevant information gain is intentionally the dominant signal.

    Research value is not:
      - candidate quality,
      - evidence truth,
      - probability,
      - recommendation confidence.
    """

    iteration_status = getattr(
        iteration,
        "status",
        None,
    )

    if iteration_status != "completed":
        return _set_unknown(
            iteration,
            "iteration_not_completed_or_unobservable",
        )

    retrieval = str(
        getattr(
            iteration,
            "retrieval_yield_status",
            "UNKNOWN",
        )
        or "UNKNOWN"
    ).upper()

    saturation = str(
        getattr(
            iteration,
            "evidence_saturation_status",
            "UNKNOWN",
        )
        or "UNKNOWN"
    ).upper()

    information = str(
        getattr(
            iteration,
            "information_gain_status",
            "UNKNOWN",
        )
        or "UNKNOWN"
    ).upper()

    reasons = [
        f"retrieval yield: {retrieval.lower()}",
        f"evidence saturation: {saturation.lower()}",
        f"decision information gain: {information.lower()}",
    ]

    # Missing decision-information observability must never be interpreted
    # as low value.
    if information == "UNKNOWN":
        return _set_unknown(
            iteration,
            "decision information gain unavailable",
            extra_reasons=reasons,
        )

    # HIGH decision information always represents high research value.
    # Even saturated evidence can still close a previously uncovered
    # candidate×criterion pair.
    if information == "HIGH_INFORMATION_GAIN":
        status = "HIGH_VALUE"

    # New directional decision information is materially useful even if
    # retrieval volume itself is modest.
    elif information == "MODERATE_INFORMATION_GAIN":
        status = "MODERATE_VALUE"

    # Some claim novelty exists, but it did not materially expand the
    # decision state.
    elif information == "LOW_INFORMATION_GAIN":
        status = "LOW_VALUE"

    # No decision information gain. Distinguish some retrieval activity
    # from complete lack of useful marginal progress.
    elif information == "NO_INFORMATION_GAIN":
        if (
            retrieval
            in {
                "HIGH_YIELD",
                "MODERATE_YIELD",
            }
            and saturation == "LOW_SATURATION"
        ):
            status = "LOW_VALUE"
            reasons.append(
                "retrieval added material but no new decision information"
            )
        else:
            status = "NO_VALUE"
            reasons.append(
                "iteration added no material decision-relevant knowledge"
            )

    else:
        return _set_unknown(
            iteration,
            "unrecognized information gain status",
            extra_reasons=reasons,
        )

    iteration.adaptive_research_value_status = (
        status
    )
    iteration.adaptive_research_value_reasons = (
        reasons
    )

    return status


def consecutive_low_value_count(
    iterations: list[AdaptiveResearchIteration],
) -> int:
    """
    Count consecutive LOW/NO value iterations from the tail.

    UNKNOWN and any useful-value iteration break the streak.
    """

    count = 0

    for iteration in reversed(
        iterations
    ):
        status = str(
            getattr(
                iteration,
                "adaptive_research_value_status",
                "UNKNOWN",
            )
            or "UNKNOWN"
        ).upper()

        if status in LOW_VALUE_STATUSES:
            count += 1
            continue

        break

    return count


def apply_adaptive_research_value_stop(
    stopping: ResearchStoppingDecision | None,
    iterations: list[AdaptiveResearchIteration],
    *,
    minimum_consecutive_low_value: int = 2,
) -> ResearchStoppingDecision | None:
    """
    Stop after repeated low unified adaptive-research value.

    Existing stronger stop reasons remain untouched.

    The reason remains ``diminishing_returns`` for API/replay compatibility
    with Phase 29, but the policy now consumes Phase-32 research value.
    """

    if stopping is None:
        return None

    latest_status = (
        str(
            getattr(
                iterations[-1],
                "adaptive_research_value_status",
                "UNKNOWN",
            )
            or "UNKNOWN"
        )
        if iterations
        else "UNKNOWN"
    )

    count = consecutive_low_value_count(
        iterations
    )

    stopping.adaptive_research_value_status = (
        latest_status
    )
    stopping.consecutive_low_value_iterations = (
        count
    )

    # Keep legacy diagnostic fields synchronized for replay/API compatibility.
    if iterations:
        stopping.retrieval_yield_status = str(
            getattr(
                iterations[-1],
                "retrieval_yield_status",
                "UNKNOWN",
            )
            or "UNKNOWN"
        )

    stopping.consecutive_low_yield_iterations = (
        count
    )

    if not stopping.should_continue:
        return stopping

    if count < minimum_consecutive_low_value:
        return stopping

    stopping.should_continue = False
    stopping.reason = "diminishing_returns"

    return stopping


def _set_unknown(
    iteration: AdaptiveResearchIteration,
    reason: str,
    *,
    extra_reasons: list[str] | None = None,
) -> str:
    iteration.adaptive_research_value_status = (
        "UNKNOWN"
    )

    reasons = list(
        extra_reasons
        or []
    )

    reasons.append(
        reason
    )

    iteration.adaptive_research_value_reasons = (
        reasons
    )

    return "UNKNOWN"
