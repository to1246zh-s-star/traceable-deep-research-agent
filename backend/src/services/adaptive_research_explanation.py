"""Deterministic explanation of adaptive research value and stopping."""

from __future__ import annotations

from models import (
    AdaptiveResearchIteration,
    ResearchStoppingDecision,
)


def build_adaptive_research_explanation(
    iteration: AdaptiveResearchIteration,
    stopping: ResearchStoppingDecision | None,
) -> AdaptiveResearchIteration:
    """
    Attach a stable replay-friendly explanation to one adaptive iteration.

    This service explains existing Phase 29–32 outputs only.
    It never changes research value, evidence interpretation, or stopping.
    """

    value = _status(
        getattr(
            iteration,
            "adaptive_research_value_status",
            "UNKNOWN",
        )
    )

    retrieval = _status(
        getattr(
            iteration,
            "retrieval_yield_status",
            "UNKNOWN",
        )
    )

    saturation = _status(
        getattr(
            iteration,
            "evidence_saturation_status",
            "UNKNOWN",
        )
    )

    information = _status(
        getattr(
            iteration,
            "information_gain_status",
            "UNKNOWN",
        )
    )

    iteration.research_value_summary = (
        _value_summary(
            value
        )
    )

    iteration.research_value_explanation = [
        f"retrieval yield: {retrieval.lower()}",
        f"evidence saturation: {saturation.lower()}",
        (
            "decision information gain: "
            f"{information.lower()}"
        ),
        (
            "adaptive research value: "
            f"{value.lower()}"
        ),
    ]

    iteration.research_value_observations = (
        _build_observations(
            iteration
        )
    )

    iteration.stopping_explanation = (
        _build_stopping_explanation(
            stopping
        )
    )

    return iteration


def _value_summary(
    value: str,
) -> str:
    summaries = {
        "HIGH_VALUE": (
            "This research iteration materially expanded "
            "the decision-relevant knowledge state."
        ),
        "MODERATE_VALUE": (
            "This research iteration added useful "
            "decision-relevant information."
        ),
        "LOW_VALUE": (
            "This research iteration added limited "
            "decision-relevant value."
        ),
        "NO_VALUE": (
            "This research iteration added no material "
            "decision-relevant value."
        ),
        "UNKNOWN": (
            "Research value could not be determined "
            "from the available iteration state."
        ),
    }

    return summaries.get(
        value,
        summaries["UNKNOWN"],
    )


def _build_observations(
    iteration: AdaptiveResearchIteration,
) -> list[str]:
    observations: list[str] = []

    new_evidence_count = int(
        getattr(
            iteration,
            "new_evidence_count",
            0,
        )
        or 0
    )

    if new_evidence_count:
        observations.append(
            f"{new_evidence_count} new evidence item(s)"
        )

    unique_source_count = int(
        getattr(
            iteration,
            "new_unique_source_count",
            0,
        )
        or 0
    )

    if unique_source_count:
        observations.append(
            (
                f"{unique_source_count} "
                "new unique source URL(s)"
            )
        )

    novel_content_count = int(
        getattr(
            iteration,
            "novel_content_count",
            0,
        )
        or 0
    )

    if novel_content_count:
        observations.append(
            (
                f"{novel_content_count} "
                "lexically novel evidence item(s)"
            )
        )

    novel_claim_count = int(
        getattr(
            iteration,
            "novel_claim_count",
            0,
        )
        or 0
    )

    if novel_claim_count:
        observations.append(
            f"{novel_claim_count} novel claim(s)"
        )

    new_signal_count = int(
        getattr(
            iteration,
            "new_directional_signal_count",
            0,
        )
        or 0
    )

    if new_signal_count:
        observations.append(
            (
                f"{new_signal_count} new directional "
                "decision signal(s)"
            )
        )

    new_pairs = list(
        getattr(
            iteration,
            "new_candidate_criterion_pairs",
            [],
        )
        or []
    )

    if new_pairs:
        observations.append(
            (
                f"{len(new_pairs)} newly covered "
                "candidate×criterion pair(s)"
            )
        )

    duplicate_domain_ratio = float(
        getattr(
            iteration,
            "duplicate_domain_ratio",
            0.0,
        )
        or 0.0
    )

    if duplicate_domain_ratio > 0:
        observations.append(
            (
                "duplicate-domain ratio: "
                f"{duplicate_domain_ratio:.2f}"
            )
        )

    near_duplicate_ratio = float(
        getattr(
            iteration,
            "near_duplicate_content_ratio",
            0.0,
        )
        or 0.0
    )

    if near_duplicate_ratio > 0:
        observations.append(
            (
                "near-duplicate content ratio: "
                f"{near_duplicate_ratio:.2f}"
            )
        )

    claim_novelty_ratio = float(
        getattr(
            iteration,
            "claim_novelty_ratio",
            0.0,
        )
        or 0.0
    )

    if claim_novelty_ratio > 0:
        observations.append(
            (
                "claim novelty ratio: "
                f"{claim_novelty_ratio:.2f}"
            )
        )

    if not observations:
        observations.append(
            "no additional quantitative observations available"
        )

    return observations


def _build_stopping_explanation(
    stopping: ResearchStoppingDecision | None,
) -> str:
    if stopping is None:
        return (
            "No stopping decision was available "
            "after this iteration."
        )

    reason = str(
        getattr(
            stopping,
            "reason",
            "",
        )
        or ""
    ).strip()

    should_continue = bool(
        getattr(
            stopping,
            "should_continue",
            False,
        )
    )

    if should_continue:
        if reason:
            return (
                "Adaptive research continues; "
                f"current stopping reason: {reason}."
            )

        return (
            "Adaptive research continues after this iteration."
        )

    if reason == "diminishing_returns":
        count = int(
            getattr(
                stopping,
                "consecutive_low_value_iterations",
                0,
            )
            or 0
        )

        return (
            "Adaptive research stopped because marginal "
            "research value showed diminishing returns "
            f"across {count} consecutive low-value iteration(s)."
        )

    if reason:
        return (
            "Adaptive research stopped; "
            f"reason: {reason}."
        )

    return (
        "Adaptive research stopped after this iteration."
    )


def _status(
    value: object,
) -> str:
    text = str(
        value
        or "UNKNOWN"
    ).strip().upper()

    return (
        text
        or "UNKNOWN"
    )
