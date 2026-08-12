"""Internal knowledge and hybrid retrieval baseline for V3 Phase 15."""

import re
from urllib.parse import urlsplit, urlunsplit

from models import (
    Evidence,
    HybridRetrievalResult,
    InternalDocument,
    InternalRetrievalHit,
)


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_+#.-]{2,}")


def tokenize(text: str) -> set[str]:
    """Return normalized lexical tokens for deterministic retrieval."""

    tokens: set[str] = set()

    for raw_token in TOKEN_PATTERN.findall(text or ""):
        token = raw_token.lower().strip(".-")

        if token:
            tokens.add(token)

    return tokens


def retrieve_internal_documents(
    query: str,
    documents: list[InternalDocument],
    *,
    top_k: int = 5,
) -> list[InternalRetrievalHit]:
    """
    Rank internal documents with an explainable lexical-overlap baseline.

    This is intentionally deterministic. A vector/embedding retriever can
    replace this implementation later without changing its output contract.
    """

    if top_k <= 0:
        return []

    query_terms = tokenize(query)

    if not query_terms:
        return []

    hits: list[InternalRetrievalHit] = []

    for document in documents:
        document_terms = tokenize(
            " ".join(
                [
                    document.title,
                    document.content,
                    " ".join(
                        f"{key} {value}"
                        for key, value in document.metadata.items()
                    ),
                ]
            )
        )

        matched_terms = sorted(
            query_terms & document_terms
        )

        if not matched_terms:
            continue

        # Query coverage is the primary score.
        query_coverage = (
            len(matched_terms)
            / len(query_terms)
        )

        # Small title-match bonus rewards focused internal documents.
        title_terms = tokenize(document.title)

        title_match_ratio = (
            len(query_terms & title_terms)
            / len(query_terms)
        )

        score = min(
            1.0,
            query_coverage
            + 0.15 * title_match_ratio,
        )

        hits.append(
            InternalRetrievalHit(
                document_id=document.document_id,
                score=score,
                matched_terms=matched_terms,
            )
        )

    hits.sort(
        key=lambda hit: (
            -hit.score,
            hit.document_id,
        )
    )

    return hits[:top_k]


def internal_hits_to_evidence(
    query: str,
    documents: list[InternalDocument],
    hits: list[InternalRetrievalHit],
    *,
    task_id: int,
    trace_id: str,
) -> list[Evidence]:
    """Convert internal retrieval hits into the existing Evidence model."""

    documents_by_id = {
        document.document_id: document
        for document in documents
    }

    evidence_items: list[Evidence] = []

    for rank, hit in enumerate(
        hits,
        start=1,
    ):
        document = documents_by_id.get(
            hit.document_id
        )

        if document is None:
            raise ValueError(
                f"unknown internal document {hit.document_id!r}"
            )

        source_url = (
            f"internal://{document.document_id}"
        )

        snippet = document.content[:500]

        evidence_items.append(
            Evidence(
                task_id=task_id,
                trace_id=trace_id,
                query=query,
                backend="internal",
                source_title=document.title,
                source_url=source_url,
                snippet=snippet,
                content=document.content,
                source_rank=rank,
            )
        )

    return evidence_items


def normalize_source_identity(
    evidence: Evidence,
) -> str:
    """Build deterministic source identity for hybrid deduplication."""

    source_url = (
        evidence.source_url
        or ""
    ).strip()

    if source_url:
        if source_url.startswith("internal://"):
            return source_url.lower()

        parsed = urlsplit(source_url)

        normalized = urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                parsed.query,
                "",
            )
        )

        return normalized.lower()

    title = (
        evidence.source_title
        or ""
    ).strip().lower()

    content = (
        evidence.content
        or evidence.snippet
        or ""
    ).strip().lower()

    return f"{title}|{content[:200]}"


def _evidence_priority(
    evidence: Evidence,
) -> tuple[int, int]:
    """
    Deterministic ordering without pretending internal is always superior.

    Lower source_rank is preferred. Internal/external origin is only used
    as a stable secondary ordering key.
    """

    rank = (
        evidence.source_rank
        if evidence.source_rank is not None
        else 10**9
    )

    origin_order = (
        0
        if evidence.backend == "internal"
        else 1
    )

    return (
        rank,
        origin_order,
    )


def merge_hybrid_evidence(
    query: str,
    *,
    external_evidence: list[Evidence],
    internal_evidence: list[Evidence],
    max_results: int | None = None,
) -> HybridRetrievalResult:
    """
    Merge internal and external Evidence into one provenance-preserving list.

    Duplicate sources are collapsed by normalized source identity.
    """

    combined = [
        *internal_evidence,
        *external_evidence,
    ]

    combined.sort(
        key=_evidence_priority
    )

    deduplicated: list[Evidence] = []
    seen: set[str] = set()
    duplicate_count = 0

    for evidence in combined:
        identity = normalize_source_identity(
            evidence
        )

        if identity in seen:
            duplicate_count += 1
            continue

        seen.add(identity)
        deduplicated.append(evidence)

    if max_results is not None:
        if max_results < 0:
            raise ValueError(
                "max_results must be non-negative"
            )

        deduplicated = deduplicated[
            :max_results
        ]

    return HybridRetrievalResult(
        query=query,
        evidence_items=deduplicated,
        internal_count=sum(
            1
            for evidence in deduplicated
            if evidence.backend == "internal"
        ),
        external_count=sum(
            1
            for evidence in deduplicated
            if evidence.backend != "internal"
        ),
        duplicate_count=duplicate_count,
    )


def hybrid_retrieve(
    query: str,
    *,
    documents: list[InternalDocument],
    external_evidence: list[Evidence],
    task_id: int,
    trace_id: str,
    internal_top_k: int = 5,
    max_results: int | None = None,
) -> HybridRetrievalResult:
    """Run internal retrieval and merge it with externally retrieved Evidence."""

    hits = retrieve_internal_documents(
        query,
        documents,
        top_k=internal_top_k,
    )

    internal_evidence = internal_hits_to_evidence(
        query,
        documents,
        hits,
        task_id=task_id,
        trace_id=trace_id,
    )

    return merge_hybrid_evidence(
        query,
        external_evidence=external_evidence,
        internal_evidence=internal_evidence,
        max_results=max_results,
    )
