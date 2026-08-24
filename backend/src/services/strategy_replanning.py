"""Strategy-aware deterministic query planning for adaptive research."""

from __future__ import annotations

from models import ResearchGap


SOURCE_TYPE_QUERY_TERMS = {
    "official_documentation": (
        "official documentation"
    ),
    "official_security_documentation": (
        "official security documentation"
    ),
    "official_pricing_documentation": (
        "official pricing documentation"
    ),
    "release_notes": (
        "official release notes"
    ),
    "source_repository": (
        "source code repository"
    ),
    "issue_tracker": (
        "issue tracker"
    ),
    "academic_paper": (
        "academic paper"
    ),
    "benchmark": (
        "independent benchmark"
    ),
    "independent_engineering_review": (
        "independent engineering review"
    ),
    "independent_source": (
        "independent source"
    ),
    "security_advisory": (
        "security advisory"
    ),
    "cve": "CVE",
    "cost_comparison": (
        "cost comparison"
    ),
    "community": (
        "community experience"
    ),
    "news": (
        "news"
    ),
}


def build_effective_followup_query(
    gap: ResearchGap,
) -> str | None:
    """
    Return the query that should actually be executed for one gap.

    FULL strategy coverage needs no source-strategy follow-up.
    PARTIAL/NONE target only missing source categories.
    UNKNOWN preserves the existing generic query.
    """

    status = (
        gap.strategy_match_status
        or "UNKNOWN"
    ).upper()

    if status == "FULL":
        return None

    if (
        status in {"PARTIAL", "NONE"}
        and gap.missing_source_types
    ):
        return _build_targeted_query(
            gap
        )

    return _clean(
        gap.suggested_query
        or gap.description
    ) or None


def is_strategy_reroute(
    gap: ResearchGap,
) -> bool:
    """
    Return whether an already-executed logical gap may be revisited.

    The gap itself may be old, but newly missing source categories can
    produce a genuinely different follow-up query.
    """

    status = (
        gap.strategy_match_status
        or "UNKNOWN"
    ).upper()

    return (
        status in {"PARTIAL", "NONE"}
        and bool(
            gap.missing_source_types
        )
    )


def _build_targeted_query(
    gap: ResearchGap,
) -> str | None:
    base_query = _strip_strategy_suffix(
        _clean(
            gap.suggested_query
            or gap.description
        ),
        gap.query_qualifiers,
    )

    parts: list[str] = []

    if base_query:
        parts.append(base_query)

    for source_type in gap.missing_source_types:
        qualifier = (
            SOURCE_TYPE_QUERY_TERMS.get(
                source_type,
                _fallback_source_term(
                    source_type
                ),
            )
        )

        if not qualifier:
            continue

        # Avoid adding a qualifier already represented in the remaining
        # base query.
        existing_text = " ".join(
            parts
        ).casefold()

        if (
            qualifier.casefold()
            in existing_text
        ):
            continue

        parts.append(
            qualifier
        )

    return _join_unique(
        parts
    ) or None


def _strip_strategy_suffix(
    query: str,
    qualifiers: list[str],
) -> str:
    """
    Remove only Phase-25 qualifiers appended at the end of the query.

    Do not globally replace words such as "performance", because those
    words may be part of the original criterion itself.
    """

    result = _clean(
        query
    )

    for qualifier in reversed(
        qualifiers
    ):
        value = _clean(
            qualifier
        )

        if (
            not result
            or not value
        ):
            continue

        result_folded = (
            result.casefold()
        )
        value_folded = (
            value.casefold()
        )

        if result_folded == value_folded:
            result = ""
            continue

        suffix = (
            " " + value_folded
        )

        if result_folded.endswith(
            suffix
        ):
            result = result[
                : -len(value)
            ].rstrip()

    return result


def _fallback_source_term(
    source_type: str,
) -> str:
    return _clean(
        source_type.replace(
            "_",
            " ",
        )
    )


def _join_unique(
    parts: list[str],
) -> str:
    result: list[str] = []
    seen: set[str] = set()

    for part in parts:
        value = _clean(
            part
        )

        if not value:
            continue

        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return " ".join(
        result
    )


def _clean(
    value: str | None,
) -> str:
    return " ".join(
        str(
            value
            or ""
        ).strip().split()
    )
