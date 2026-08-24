"""Evaluate whether retrieved evidence satisfied planned source strategies."""

from __future__ import annotations

from models import (
    EvidenceAssessment,
    EvidenceSignal,
    ResearchGap,
)


AUTHORITY_TO_SOURCE_TYPES = {
    "OFFICIAL_DOCUMENTATION": {
        "official_documentation",
    },
    "OFFICIAL_SECURITY": {
        "official_documentation",
        "official_security_documentation",
    },
    "OFFICIAL_PRICING": {
        "official_documentation",
        "official_pricing_documentation",
    },
    "OFFICIAL_RELEASE_NOTES": {
        "official_documentation",
        "release_notes",
    },
    "SOURCE_REPOSITORY": {
        "source_repository",
    },
    "ISSUE_TRACKER": {
        "issue_tracker",
    },
    "ACADEMIC": {
        "academic_paper",
    },
    "INDEPENDENT_BENCHMARK": {
        "benchmark",
    },
    "INDEPENDENT_TECHNICAL": {
        "independent_engineering_review",
        "independent_source",
    },
    "COMMUNITY": {
        "community",
    },
    "NEWS": {
        "news",
    },
}


def evaluate_source_strategy_matches(
    gaps: list[ResearchGap],
    signals: list[EvidenceSignal],
    assessments: list[EvidenceAssessment],
) -> list[ResearchGap]:
    """
    Attach deterministic Phase 27 retrieval-effectiveness metadata.

    Matching is based only on actual evidence linked to the same
    candidate × criterion through EvidenceSignal objects.
    """

    assessments_by_id = {
        item.evidence_id: item
        for item in assessments
    }

    signals_by_pair: dict[
        tuple[str, str],
        list[EvidenceSignal],
    ] = {}

    for signal in signals:
        key = (
            signal.candidate_id,
            signal.criterion_id,
        )

        signals_by_pair.setdefault(
            key,
            [],
        ).append(signal)

    for gap in gaps:
        _evaluate_gap(
            gap,
            signals_by_pair=signals_by_pair,
            assessments_by_id=assessments_by_id,
        )

    return gaps


def _evaluate_gap(
    gap: ResearchGap,
    *,
    signals_by_pair: dict[
        tuple[str, str],
        list[EvidenceSignal],
    ],
    assessments_by_id: dict[
        str,
        EvidenceAssessment,
    ],
) -> None:
    preferred = _dedupe(
        gap.preferred_source_types
    )

    # No planned strategy means there is nothing meaningful to compare.
    if not preferred:
        _set_unknown(
            gap
        )
        return

    pair = (
        gap.candidate_id,
        gap.criterion_id,
    )

    pair_signals = signals_by_pair.get(
        pair,
        [],
    )

    if not pair_signals:
        gap.strategy_match_status = "NONE"
        gap.matched_source_types = []
        gap.missing_source_types = list(
            preferred
        )
        gap.observed_authority_types = []
        gap.strategy_matched_evidence_ids = []
        return

    observed_authorities: list[str] = []
    observed_source_types: set[str] = set()
    matched_evidence_ids: list[str] = []

    preferred_set = set(
        preferred
    )

    for signal in pair_signals:
        assessment = assessments_by_id.get(
            signal.evidence_id
        )

        if assessment is None:
            continue

        authority_type = (
            assessment
            .source_quality
            .authority_type
        )

        if (
            not authority_type
            or authority_type == "UNKNOWN"
        ):
            continue

        observed_authorities.append(
            authority_type
        )

        source_types = (
            AUTHORITY_TO_SOURCE_TYPES.get(
                authority_type,
                set(),
            )
        )

        observed_source_types.update(
            source_types
        )

        if (
            preferred_set
            & source_types
        ):
            matched_evidence_ids.append(
                signal.evidence_id
            )

    observed_authorities = _dedupe(
        observed_authorities
    )

    matched = [
        item
        for item in preferred
        if item in observed_source_types
    ]

    missing = [
        item
        for item in preferred
        if item not in observed_source_types
    ]

    gap.matched_source_types = matched
    gap.missing_source_types = missing
    gap.observed_authority_types = (
        observed_authorities
    )
    gap.strategy_matched_evidence_ids = (
        _dedupe(
            matched_evidence_ids
        )
    )

    if not observed_authorities:
        # Evidence may exist, but authority was not recognized.
        gap.strategy_match_status = "UNKNOWN"
        return

    if len(matched) == len(preferred):
        gap.strategy_match_status = "FULL"
        return

    if matched:
        gap.strategy_match_status = "PARTIAL"
        return

    gap.strategy_match_status = "NONE"


def _set_unknown(
    gap: ResearchGap,
) -> None:
    gap.strategy_match_status = "UNKNOWN"
    gap.matched_source_types = []
    gap.missing_source_types = []
    gap.observed_authority_types = []
    gap.strategy_matched_evidence_ids = []


def _dedupe(
    values: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for raw_value in values:
        value = str(
            raw_value
        ).strip()

        if not value:
            continue

        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result
