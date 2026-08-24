"""Deterministic evidence saturation and redundancy analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from models import (
    AdaptiveResearchIteration,
    Evidence,
)


NEAR_DUPLICATE_THRESHOLD = 0.85

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


@dataclass(kw_only=True)
class EvidenceSaturationSnapshot:
    evidence_items: list[Evidence] = field(
        default_factory=list
    )


def capture_evidence_saturation_snapshot(
    evidence_items: list[Evidence],
) -> EvidenceSaturationSnapshot:
    """Capture evidence present before or after one adaptive iteration."""

    return EvidenceSaturationSnapshot(
        evidence_items=list(
            evidence_items
        )
    )


def assess_iteration_evidence_saturation(
    iteration: AdaptiveResearchIteration,
    before: EvidenceSaturationSnapshot,
    after: EvidenceSaturationSnapshot,
) -> str:
    """
    Assess redundancy among evidence newly added during one iteration.

    Saturation describes retrieval redundancy only. It does not assess
    factual truth, candidate quality, or source authority.
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

    before_by_id = {
        item.evidence_id: item
        for item in before.evidence_items
    }

    new_items = [
        item
        for item in after.evidence_items
        if item.evidence_id not in before_by_id
    ]

    if not new_items:
        return _set_unknown(
            iteration,
            "no_new_evidence_to_assess",
        )

    before_urls = {
        canonicalize_url(
            item.source_url
        )
        for item in before.evidence_items
        if canonicalize_url(
            item.source_url
        )
    }

    before_domains = {
        source_domain(
            item.source_url
        )
        for item in before.evidence_items
        if source_domain(
            item.source_url
        )
    }

    seen_urls = set(
        before_urls
    )

    seen_domains = set(
        before_domains
    )

    previous_token_sets = [
        evidence_tokens(item)
        for item in before.evidence_items
        if evidence_tokens(item)
    ]

    duplicate_domain_count = 0
    near_duplicate_count = 0
    novel_content_count = 0
    new_unique_source_count = 0

    for item in new_items:
        url = canonicalize_url(
            item.source_url
        )

        domain = source_domain(
            item.source_url
        )

        if domain and domain in seen_domains:
            duplicate_domain_count += 1

        if domain:
            seen_domains.add(
                domain
            )

        if url and url not in seen_urls:
            new_unique_source_count += 1
            seen_urls.add(
                url
            )

        tokens = evidence_tokens(
            item
        )

        is_near_duplicate = False

        if tokens:
            for previous in previous_token_sets:
                if (
                    jaccard_similarity(
                        tokens,
                        previous,
                    )
                    >= NEAR_DUPLICATE_THRESHOLD
                ):
                    is_near_duplicate = True
                    break

        if is_near_duplicate:
            near_duplicate_count += 1
        else:
            novel_content_count += 1

        if tokens:
            # New evidence also becomes part of the comparison baseline,
            # so duplicates within the same adaptive batch are detected.
            previous_token_sets.append(
                tokens
            )

    new_count = len(
        new_items
    )

    duplicate_domain_ratio = (
        duplicate_domain_count
        / new_count
    )

    near_duplicate_content_ratio = (
        near_duplicate_count
        / new_count
    )

    iteration.new_unique_source_count = (
        new_unique_source_count
    )

    iteration.novel_content_count = (
        novel_content_count
    )

    iteration.duplicate_domain_ratio = round(
        duplicate_domain_ratio,
        4,
    )

    iteration.near_duplicate_content_ratio = round(
        near_duplicate_content_ratio,
        4,
    )

    reasons: list[str] = [
        f"{new_count} new evidence item(s)",
        (
            f"{new_unique_source_count} "
            "new unique source URL(s)"
        ),
        (
            f"{novel_content_count} "
            "lexically novel evidence item(s)"
        ),
    ]

    # Content repetition is the stronger saturation signal.
    if near_duplicate_content_ratio >= 0.60:
        status = "HIGH_SATURATION"

        reasons.append(
            "most new evidence is near-duplicate content"
        )

    elif (
        near_duplicate_content_ratio >= 0.30
        or duplicate_domain_ratio >= 0.75
    ):
        status = "MODERATE_SATURATION"

        if near_duplicate_content_ratio >= 0.30:
            reasons.append(
                "material near-duplicate content detected"
            )

        if duplicate_domain_ratio >= 0.75:
            reasons.append(
                "most new evidence comes from already-seen domains"
            )

    else:
        status = "LOW_SATURATION"

        reasons.append(
            "new evidence remains materially diverse"
        )

    iteration.evidence_saturation_status = (
        status
    )

    iteration.saturation_reasons = (
        reasons
    )

    return status


def canonicalize_url(
    url: str | None,
) -> str:
    value = str(
        url
        or ""
    ).strip()

    if not value:
        return ""

    try:
        parsed = urlsplit(
            value
        )
    except ValueError:
        return value.casefold()

    hostname = (
        parsed.hostname
        or ""
    ).casefold()

    if hostname.startswith(
        "www."
    ):
        hostname = hostname[4:]

    if not hostname:
        return value.casefold()

    port = parsed.port

    netloc = hostname

    if (
        port is not None
        and not (
            parsed.scheme.casefold() == "http"
            and port == 80
        )
        and not (
            parsed.scheme.casefold() == "https"
            and port == 443
        )
    ):
        netloc = (
            f"{hostname}:{port}"
        )

    query_pairs = []

    for key, query_value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):
        normalized_key = key.casefold()

        if (
            normalized_key.startswith(
                "utm_"
            )
            or normalized_key
            in TRACKING_QUERY_KEYS
        ):
            continue

        query_pairs.append(
            (
                key,
                query_value,
            )
        )

    query_pairs.sort()

    path = (
        parsed.path
        or "/"
    )

    if path != "/":
        path = path.rstrip(
            "/"
        )

    return urlunsplit(
        (
            parsed.scheme.casefold(),
            netloc,
            path,
            urlencode(
                query_pairs
            ),
            "",
        )
    )


def source_domain(
    url: str | None,
) -> str:
    value = str(
        url
        or ""
    ).strip()

    if not value:
        return ""

    try:
        hostname = (
            urlsplit(value).hostname
            or ""
        ).casefold()
    except ValueError:
        return ""

    if hostname.startswith(
        "www."
    ):
        hostname = hostname[4:]

    return hostname


def evidence_tokens(
    evidence: Evidence,
) -> set[str]:
    """
    Return lexical content tokens for redundancy detection.

    Prefer evidence body text. Source titles are metadata and may differ
    across mirrors of identical content, so they must not dilute body
    similarity. Fall back to the title only when no body text exists.
    """

    body_text = " ".join(
        part
        for part in [
            evidence.snippet,
            evidence.content,
        ]
        if part
    ).strip()

    text = (
        body_text
        or str(
            evidence.source_title
            or ""
        ).strip()
    )

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        text.casefold(),
    )

    return {
        token
        for token in normalized.split()
        if len(token) >= 3
    }


def jaccard_similarity(
    left: set[str],
    right: set[str],
) -> float:
    if not left or not right:
        return 0.0

    union = (
        left
        | right
    )

    if not union:
        return 0.0

    return len(
        left & right
    ) / len(
        union
    )


def enrich_retrieval_yield_with_saturation(
    iteration: AdaptiveResearchIteration,
) -> None:
    """
    Add saturation context to Phase-29 explanations.

    Do not change retrieval_yield_status or stopping behavior here.
    """

    status = (
        iteration.evidence_saturation_status
        or "UNKNOWN"
    )

    if status == "UNKNOWN":
        return

    message = (
        "evidence saturation: "
        f"{status.lower()}"
    )

    if (
        message
        not in iteration.retrieval_yield_reasons
    ):
        iteration.retrieval_yield_reasons.append(
            message
        )


def _set_unknown(
    iteration: AdaptiveResearchIteration,
    reason: str,
) -> str:
    iteration.evidence_saturation_status = (
        "UNKNOWN"
    )

    iteration.new_unique_source_count = 0
    iteration.novel_content_count = 0
    iteration.duplicate_domain_ratio = 0.0
    iteration.near_duplicate_content_ratio = 0.0

    iteration.saturation_reasons = [
        reason
    ]

    return "UNKNOWN"
