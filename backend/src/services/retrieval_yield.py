"""Deterministic marginal-yield analysis for adaptive retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

from models import (
    AdaptiveResearchIteration,
    ResearchStoppingDecision,
    SummaryState,
)


LOW_YIELD_STATUSES = {
    "LOW_YIELD",
    "NO_YIELD",
}


@dataclass(kw_only=True)
class RetrievalSnapshot:
    evidence_ids: set[str] = field(
        default_factory=set
    )
    authority_types: set[str] = field(
        default_factory=set
    )
    strategy_matches: set[str] = field(
        default_factory=set
    )
    open_gap_count: int = 0


def capture_retrieval_snapshot(
    state: SummaryState,
) -> RetrievalSnapshot:
    """Capture only deterministic state needed for marginal-yield comparison."""

    evidence_ids = {
        item.evidence_id
        for item in state.evidence_items
    }

    authority_types = {
        assessment.source_quality.authority_type
        for assessment in state.evidence_assessments
        if (
            assessment.source_quality.authority_type
            and assessment.source_quality.authority_type
            != "UNKNOWN"
        )
    }

    strategy_matches: set[str] = set()

    analysis = state.research_analysis

    if analysis is not None:
        for gap in analysis.research_gaps:
            for source_type in (
                gap.matched_source_types
            ):
                strategy_matches.add(
                    _strategy_match_key(
                        gap.candidate_id,
                        gap.criterion_id,
                        source_type,
                    )
                )

        open_gap_count = sum(
            1
            for gap in analysis.research_gaps
            if gap.status == "open"
        )
    else:
        open_gap_count = 0

    return RetrievalSnapshot(
        evidence_ids=evidence_ids,
        authority_types=authority_types,
        strategy_matches=strategy_matches,
        open_gap_count=open_gap_count,
    )


def assess_iteration_retrieval_yield(
    iteration: AdaptiveResearchIteration,
    before: RetrievalSnapshot,
    after: RetrievalSnapshot,
) -> str:
    """
    Attach and return categorical marginal retrieval yield.

    Priority:
      useful strategy coverage > authority novelty > raw evidence volume.

    This is not a probability and never evaluates candidate quality.
    """

    iteration_status = getattr(
        iteration,
        "status",
        None,
    )

    if iteration_status is None:
        _set_unknown(
            iteration,
            before,
            after,
            "iteration_status_unavailable",
        )
        return iteration.retrieval_yield_status

    if iteration_status != "completed":
        _set_unknown(
            iteration,
            before,
            after,
            "iteration_not_completed",
        )
        return iteration.retrieval_yield_status

    new_evidence = sorted(
        after.evidence_ids
        - before.evidence_ids
    )

    new_authorities = sorted(
        after.authority_types
        - before.authority_types
    )

    new_matches = sorted(
        after.strategy_matches
        - before.strategy_matches
    )

    iteration.new_evidence_count = len(
        new_evidence
    )
    iteration.new_authority_types = (
        new_authorities
    )
    iteration.new_strategy_matches = (
        new_matches
    )
    iteration.gap_count_before = (
        before.open_gap_count
    )
    iteration.gap_count_after = (
        after.open_gap_count
    )

    reasons: list[str] = []

    if new_matches:
        reasons.append(
            f"{len(new_matches)} new strategy source match(es)"
        )

    if new_authorities:
        reasons.append(
            f"{len(new_authorities)} new authority type(s)"
        )

    if new_evidence:
        reasons.append(
            f"{len(new_evidence)} new evidence item(s)"
        )

    gap_reduction = max(
        0,
        before.open_gap_count
        - after.open_gap_count,
    )

    if gap_reduction:
        reasons.append(
            f"{gap_reduction} open research gap(s) resolved"
        )

    # Strongest signal: multiple useful strategy categories or
    # strategy coverage plus actual gap reduction.
    if (
        len(new_matches) >= 2
        or (
            new_matches
            and gap_reduction > 0
        )
    ):
        status = "HIGH_YIELD"

    # One useful missing source category, or meaningful authority novelty.
    elif (
        len(new_matches) == 1
        or len(new_authorities) >= 1
        or gap_reduction > 0
    ):
        status = "MODERATE_YIELD"

    # New documents arrived but they did not add source diversity,
    # strategy coverage, or resolve gaps.
    elif new_evidence:
        status = "LOW_YIELD"
        reasons.append(
            "new evidence added no new authority or strategy coverage"
        )

    else:
        status = "NO_YIELD"
        reasons.append(
            "no new evidence, authority type, or strategy coverage"
        )

    iteration.retrieval_yield_status = (
        status
    )
    iteration.retrieval_yield_reasons = (
        reasons
    )

    return status


def consecutive_low_yield_count(
    iterations: list[AdaptiveResearchIteration],
) -> int:
    """Count consecutive completed LOW/NO yield iterations from the tail."""

    count = 0

    for iteration in reversed(
        iterations
    ):
        status = (
            iteration.retrieval_yield_status
            or "UNKNOWN"
        ).upper()

        if status in LOW_YIELD_STATUSES:
            count += 1
            continue

        # UNKNOWN breaks the chain deliberately:
        # infrastructure/search failure is not evidence of diminishing value.
        break

    return count


def apply_diminishing_returns_stop(
    stopping: ResearchStoppingDecision | None,
    iterations: list[AdaptiveResearchIteration],
    *,
    minimum_consecutive_low_yield: int = 2,
) -> ResearchStoppingDecision | None:
    """
    Stop only after repeated observed low marginal retrieval yield.

    Existing stronger stop reasons remain untouched.
    """

    if stopping is None:
        return None

    count = consecutive_low_yield_count(
        iterations
    )

    latest_status = (
        iterations[-1].retrieval_yield_status
        if iterations
        else "UNKNOWN"
    )

    stopping.retrieval_yield_status = (
        latest_status
    )
    stopping.consecutive_low_yield_iterations = (
        count
    )

    # Never overwrite a stop already made for readiness, budget,
    # no actionable gaps, etc.
    if not stopping.should_continue:
        return stopping

    if count < minimum_consecutive_low_yield:
        return stopping

    stopping.should_continue = False
    stopping.reason = "diminishing_returns"

    return stopping


def _set_unknown(
    iteration: AdaptiveResearchIteration,
    before: RetrievalSnapshot,
    after: RetrievalSnapshot,
    reason: str,
) -> None:
    iteration.retrieval_yield_status = (
        "UNKNOWN"
    )
    iteration.new_evidence_count = max(
        0,
        len(after.evidence_ids)
        - len(before.evidence_ids),
    )
    iteration.new_authority_types = []
    iteration.new_strategy_matches = []
    iteration.gap_count_before = (
        before.open_gap_count
    )
    iteration.gap_count_after = (
        after.open_gap_count
    )
    iteration.retrieval_yield_reasons = [
        reason
    ]


def _strategy_match_key(
    candidate_id: str,
    criterion_id: str,
    source_type: str,
) -> str:
    return (
        f"{candidate_id}|"
        f"{criterion_id}|"
        f"{source_type}"
    )
