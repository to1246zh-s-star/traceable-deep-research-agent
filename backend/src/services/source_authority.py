"""Deterministic recognition of authority behind retrieved evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from urllib.parse import urlsplit

from models import DecisionCase, Evidence


@dataclass(kw_only=True)
class SourceAuthority:
    authority_type: str = "UNKNOWN"
    authority_level: str = "UNKNOWN"
    signals: list[str] = field(default_factory=list)


ACADEMIC_HOSTS = {
    "arxiv.org",
    "doi.org",
    "dl.acm.org",
    "ieeexplore.ieee.org",
    "link.springer.com",
    "sciencedirect.com",
    "nature.com",
    "science.org",
}

COMMUNITY_HOSTS = {
    "reddit.com",
    "www.reddit.com",
    "stackoverflow.com",
    "www.stackoverflow.com",
    "news.ycombinator.com",
}

NEWS_HOSTS = {
    "reuters.com",
    "www.reuters.com",
    "apnews.com",
    "www.apnews.com",
}

BENCHMARK_TERMS = {
    "benchmark",
    "benchmarks",
    "performance test",
    "load test",
    "throughput test",
}

SECURITY_TERMS = {
    "security",
    "security advisory",
    "advisory",
    "vulnerability",
    "cve",
}

PRICING_TERMS = {
    "pricing",
    "price",
    "plans",
    "billing",
}

RELEASE_TERMS = {
    "release notes",
    "releases",
    "changelog",
    "change log",
}


def recognize_source_authority(
    evidence: Evidence,
    decision: DecisionCase | None = None,
) -> SourceAuthority:
    """
    Recognize source authority from the actual retrieved evidence.

    The classifier is deliberately conservative:
    - search intent does not affect recognition;
    - a docs-looking URL alone does not establish vendor ownership;
    - UNKNOWN remains UNKNOWN.
    """

    hostname = _hostname(
        evidence.source_url
    )

    url_text = (
        evidence.source_url
        or ""
    ).casefold()

    title = (
        evidence.source_title
        or ""
    ).casefold()

    combined = " ".join(
        part
        for part in (
            title,
            url_text,
        )
        if part
    )

    if not hostname:
        return SourceAuthority(
            signals=[
                "missing_source_hostname"
            ]
        )

    if _host_matches(
        hostname,
        ACADEMIC_HOSTS,
    ):
        return SourceAuthority(
            authority_type="ACADEMIC",
            authority_level="HIGH",
            signals=[
                f"recognized_academic_host:{hostname}"
            ],
        )

    if _host_matches(
        hostname,
        COMMUNITY_HOSTS,
    ):
        return SourceAuthority(
            authority_type="COMMUNITY",
            authority_level="LOW",
            signals=[
                f"recognized_community_host:{hostname}"
            ],
        )

    if _host_matches(
        hostname,
        NEWS_HOSTS,
    ):
        return SourceAuthority(
            authority_type="NEWS",
            authority_level="MEDIUM",
            signals=[
                f"recognized_news_host:{hostname}"
            ],
        )

    if hostname in {
        "github.com",
        "www.github.com",
    }:
        return _classify_github(
            evidence,
            decision,
        )

    vendor_match = _match_candidate_vendor(
        hostname,
        title,
        decision,
    )

    if vendor_match is not None:
        candidate_id, candidate_name = (
            vendor_match
        )

        signals = [
            (
                "candidate_vendor_match:"
                f"{candidate_id}"
            ),
            f"hostname:{hostname}",
        ]

        if _contains_any(
            combined,
            SECURITY_TERMS,
        ):
            return SourceAuthority(
                authority_type=(
                    "OFFICIAL_SECURITY"
                ),
                authority_level="HIGH",
                signals=signals + [
                    "security_surface"
                ],
            )

        if _contains_any(
            combined,
            PRICING_TERMS,
        ):
            return SourceAuthority(
                authority_type=(
                    "OFFICIAL_PRICING"
                ),
                authority_level="HIGH",
                signals=signals + [
                    "pricing_surface"
                ],
            )

        if _contains_any(
            combined,
            RELEASE_TERMS,
        ):
            return SourceAuthority(
                authority_type=(
                    "OFFICIAL_RELEASE_NOTES"
                ),
                authority_level="HIGH",
                signals=signals + [
                    "release_surface"
                ],
            )

        return SourceAuthority(
            authority_type=(
                "OFFICIAL_DOCUMENTATION"
            ),
            authority_level="HIGH",
            signals=signals + [
                (
                    "vendor_owned_technical_"
                    "surface"
                )
            ],
        )

    if _contains_any(
        combined,
        BENCHMARK_TERMS,
    ):
        return SourceAuthority(
            authority_type=(
                "INDEPENDENT_BENCHMARK"
            ),
            authority_level="MEDIUM",
            signals=[
                "benchmark_language",
                f"hostname:{hostname}",
            ],
        )

    if _looks_technical(
        combined
    ):
        return SourceAuthority(
            authority_type=(
                "INDEPENDENT_TECHNICAL"
            ),
            authority_level="MEDIUM",
            signals=[
                "technical_source_surface",
                f"hostname:{hostname}",
            ],
        )

    return SourceAuthority(
        authority_type="UNKNOWN",
        authority_level="UNKNOWN",
        signals=[
            f"unrecognized_hostname:{hostname}"
        ],
    )


def authority_confidence(
    authority: SourceAuthority,
    *,
    legacy_confidence: float,
) -> float:
    """
    Convert categorical authority into the existing heuristic confidence.

    These are deterministic routing/weighting heuristics, not calibrated
    probabilities. Legacy confidence remains a bounded fallback.
    """

    bounded_legacy = max(
        0.0,
        min(
            1.0,
            legacy_confidence,
        ),
    )

    authority_confidence_map = {
        "OFFICIAL_DOCUMENTATION": 0.90,
        "OFFICIAL_SECURITY": 0.90,
        "OFFICIAL_PRICING": 0.90,
        "OFFICIAL_RELEASE_NOTES": 0.90,
        "SOURCE_REPOSITORY": 0.85,
        "ACADEMIC": 0.85,
        "ISSUE_TRACKER": 0.65,
        "INDEPENDENT_BENCHMARK": 0.75,
        "INDEPENDENT_TECHNICAL": 0.65,
        "NEWS": 0.60,
        "COMMUNITY": 0.40,
    }

    recognized = (
        authority_confidence_map.get(
            authority.authority_type
        )
    )

    if recognized is None:
        # UNKNOWN must not be upgraded merely because recognition failed.
        return min(
            bounded_legacy,
            0.50,
        )

    return recognized


def _classify_github(
    evidence: Evidence,
    decision: DecisionCase | None,
) -> SourceAuthority:
    url = (
        evidence.source_url
        or ""
    )

    parsed = urlsplit(url)

    parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    if len(parts) < 2:
        return SourceAuthority(
            authority_type="UNKNOWN",
            authority_level="UNKNOWN",
            signals=[
                "github_without_repository"
            ],
        )

    owner = parts[0]
    repository = parts[1]

    official = _github_repo_matches_candidate(
        owner,
        repository,
        decision,
    )

    if not official:
        return SourceAuthority(
            authority_type=(
                "INDEPENDENT_TECHNICAL"
            ),
            authority_level="MEDIUM",
            signals=[
                (
                    "github_repository_without_"
                    "candidate_match"
                )
            ],
        )

    if (
        len(parts) >= 3
        and parts[2].casefold()
        in {
            "issues",
            "discussions",
        }
    ):
        return SourceAuthority(
            authority_type="ISSUE_TRACKER",
            authority_level="MEDIUM",
            signals=[
                "candidate_repository_match",
                f"github_owner:{owner}",
                (
                    f"github_repository:"
                    f"{repository}"
                ),
            ],
        )

    return SourceAuthority(
        authority_type="SOURCE_REPOSITORY",
        authority_level="HIGH",
        signals=[
            "candidate_repository_match",
            f"github_owner:{owner}",
            (
                f"github_repository:"
                f"{repository}"
            ),
        ],
    )


def _match_candidate_vendor(
    hostname: str,
    title: str,
    decision: DecisionCase | None,
) -> tuple[str, str] | None:
    if decision is None:
        return None

    normalized_host = _normalize_identity(
        hostname
    )

    normalized_title = _normalize_identity(
        title
    )

    for candidate in decision.candidates:
        candidate_name = (
            candidate.name.strip()
        )

        candidate_identity = (
            _normalize_identity(
                candidate_name
            )
        )

        if len(candidate_identity) < 2:
            continue

        # Require candidate identity on hostname for vendor ownership.
        # Title alone is insufficient.
        if (
            candidate_identity
            in normalized_host
        ):
            return (
                candidate.candidate_id,
                candidate_name,
            )

        # Handles names like "PostgreSQL" -> postgresql.org while still
        # requiring the hostname to carry the product identity.
        compact = re.sub(
            r"[^a-z0-9]",
            "",
            candidate_identity,
        )

        if (
            len(compact) >= 4
            and compact
            in re.sub(
                r"[^a-z0-9]",
                "",
                normalized_host,
            )
        ):
            return (
                candidate.candidate_id,
                candidate_name,
            )

    return None


def _github_repo_matches_candidate(
    owner: str,
    repository: str,
    decision: DecisionCase | None,
) -> bool:
    if decision is None:
        return False

    repo_identity = (
        _normalize_identity(
            f"{owner} {repository}"
        )
    )

    for candidate in decision.candidates:
        candidate_identity = (
            _normalize_identity(
                candidate.name
            )
        )

        if (
            len(candidate_identity) >= 2
            and candidate_identity
            in repo_identity
        ):
            return True

    return False


def _hostname(
    url: str | None,
) -> str:
    if not url:
        return ""

    try:
        parsed = urlsplit(
            url.strip()
        )

        hostname = (
            parsed.hostname
            or ""
        )

        return (
            hostname
            .casefold()
            .removeprefix("www.")
        )
    except Exception:
        return ""


def _host_matches(
    hostname: str,
    hosts: set[str],
) -> bool:
    normalized_hosts = {
        item.removeprefix(
            "www."
        )
        for item in hosts
    }

    return any(
        hostname == host
        or hostname.endswith(
            "." + host
        )
        for host in normalized_hosts
    )


def _contains_any(
    text: str,
    terms: set[str],
) -> bool:
    return any(
        term in text
        for term in terms
    )


def _looks_technical(
    text: str,
) -> bool:
    terms = {
        "documentation",
        "architecture",
        "engineering",
        "technical",
        "database",
        "software",
        "deployment",
        "benchmark",
        "performance",
        "migration",
        "integration",
    }

    return _contains_any(
        text,
        terms,
    )


def _normalize_identity(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.casefold(),
    )
