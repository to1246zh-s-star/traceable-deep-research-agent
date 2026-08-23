"""Resilient search dispatch helpers leveraging HelloAgents SearchTool."""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from hello_agents.tools import SearchTool

from config import Configuration
from models import Evidence
from utils import (
    deduplicate_and_format_sources,
    format_sources,
    get_config_value,
)


logger = logging.getLogger(__name__)

MAX_TOKENS_PER_SOURCE = 2000
_GLOBAL_SEARCH_TOOL = SearchTool(backend="hybrid")

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
}


def dispatch_search(
    query: str,
    config: Configuration,
    loop_count: int,
) -> Tuple[
    dict[str, Any] | None,
    list[str],
    Optional[str],
    str,
]:
    """
    Execute the configured search backend with graceful degradation.

    Provider failure means no new evidence, not research failure.
    Structurally valid partial results are preserved.
    """

    search_api = get_config_value(
        config.search_api
    )

    try:
        raw_response = _GLOBAL_SEARCH_TOOL.run(
            {
                "input": query,
                "backend": search_api,
                "mode": "structured",
                "fetch_full_page": config.fetch_full_page,
                "max_results": 5,
                "max_tokens_per_source": MAX_TOKENS_PER_SOURCE,
                "loop_count": loop_count,
            }
        )
    except Exception as exc:
        logger.exception(
            "Search backend %s failed: %s",
            search_api,
            exc,
        )

        notice = (
            f"Search backend {search_api} failed "
            f"({type(exc).__name__}); continuing "
            f"without new web evidence."
        )

        payload: dict[str, Any] = {
            "results": [],
            "backend": search_api,
            "answer": None,
            "notices": [notice],
            "degraded": True,
            "error_type": type(exc).__name__,
        }

        return (
            payload,
            [notice],
            None,
            str(search_api),
        )

    payload = normalize_search_payload(
        raw_response,
        search_api=search_api,
    )

    notices = list(
        payload.get("notices") or []
    )

    backend_label = str(
        payload.get("backend")
        or search_api
    )

    answer_text = payload.get("answer")

    if not isinstance(answer_text, str):
        answer_text = None

    results = payload.get("results") or []

    if notices:
        for notice in notices:
            logger.info(
                "Search notice (%s): %s",
                backend_label,
                notice,
            )

    logger.info(
        (
            "Search backend=%s resolved_backend=%s "
            "answer=%s results=%s degraded=%s"
        ),
        search_api,
        backend_label,
        bool(answer_text),
        len(results),
        bool(payload.get("degraded")),
    )

    return (
        payload,
        notices,
        answer_text,
        backend_label,
    )


def normalize_search_payload(
    raw_response: Any,
    *,
    search_api: str,
) -> dict[str, Any]:
    """
    Normalize a provider response without discarding valid partial results.

    Empty results are valid and are not treated as negative evidence.
    """

    if isinstance(raw_response, str):
        notice = raw_response.strip()

        notices = (
            [notice]
            if notice
            else []
        )

        return {
            "results": [],
            "backend": search_api,
            "answer": None,
            "notices": notices,
            "degraded": True,
        }

    if not isinstance(
        raw_response,
        dict,
    ):
        notice = (
            f"Search backend {search_api} "
            "returned a malformed payload; "
            "continuing without new web evidence."
        )

        return {
            "results": [],
            "backend": search_api,
            "answer": None,
            "notices": [notice],
            "degraded": True,
            "error_type": "malformed_payload",
        }

    payload = dict(raw_response)

    backend = payload.get(
        "backend"
    )

    if not isinstance(
        backend,
        str,
    ) or not backend.strip():
        backend = search_api
    else:
        backend = backend.strip()

    answer = payload.get(
        "answer"
    )

    if not isinstance(
        answer,
        str,
    ):
        answer = None
    elif not answer.strip():
        answer = None
    else:
        answer = answer.strip()

    notices = _normalize_notices(
        payload.get("notices")
    )

    raw_results = payload.get(
        "results",
        [],
    )

    malformed_count = 0

    if raw_results is None:
        raw_results = []

    elif not isinstance(
        raw_results,
        list,
    ):
        raw_results = []
        malformed_count += 1

    (
        normalized_results,
        filtered_count,
        duplicate_count,
    ) = _normalize_results(
        raw_results
    )

    malformed_count += filtered_count

    degraded = bool(
        payload.get("degraded")
    )

    if malformed_count:
        degraded = True

        notices.append(
            (
                "Search response contained "
                f"{malformed_count} malformed "
                "result item(s); valid results "
                "were preserved."
            )
        )

    if duplicate_count:
        notices.append(
            (
                "Search response contained "
                f"{duplicate_count} duplicate "
                "result item(s); duplicates "
                "were removed."
            )
        )

    normalized = dict(payload)

    normalized.update(
        {
            "results": normalized_results,
            "backend": backend,
            "answer": answer,
            "notices": _dedupe_strings(
                notices
            ),
            "degraded": degraded,
        }
    )

    return normalized


def _normalize_results(
    raw_results: list[Any],
) -> tuple[
    list[dict[str, Any]],
    int,
    int,
]:
    results: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    malformed_count = 0
    duplicate_count = 0

    for item in raw_results:
        normalized = (
            _normalize_result_item(
                item
            )
        )

        if normalized is None:
            malformed_count += 1
            continue

        key = _result_identity(
            normalized
        )

        if key in seen:
            duplicate_count += 1
            continue

        seen.add(key)
        results.append(
            normalized
        )

    return (
        results,
        malformed_count,
        duplicate_count,
    )


def _normalize_result_item(
    item: Any,
) -> dict[str, Any] | None:
    if not isinstance(
        item,
        dict,
    ):
        return None

    normalized = dict(item)

    title = _clean_optional_text(
        item.get("title")
    )

    url = _clean_optional_text(
        item.get("url")
    )

    content = _clean_optional_text(
        item.get("content")
    )

    raw_content = _clean_optional_text(
        item.get("raw_content")
    )

    # At least one traceable/useful field must exist.
    if not any(
        (
            title,
            url,
            content,
            raw_content,
        )
    ):
        return None

    normalized["title"] = title
    normalized["url"] = url
    normalized["content"] = content
    normalized["raw_content"] = (
        raw_content
    )

    return normalized


def _result_identity(
    item: dict[str, Any],
) -> str:
    url = item.get("url")

    if url:
        canonical = (
            _canonicalize_url(url)
        )

        if canonical:
            return (
                f"url:{canonical}"
            )

    title = (
        item.get("title")
        or ""
    )

    content = (
        item.get("content")
        or item.get("raw_content")
        or ""
    )

    return (
        "content:"
        + " ".join(
            f"{title} {content}"
            .casefold()
            .split()
        )
    )


def _canonicalize_url(
    url: str,
) -> str:
    try:
        parsed = urlsplit(
            url.strip()
        )

        filtered_query = []

        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        ):
            lowered = key.casefold()

            if (
                lowered.startswith(
                    "utm_"
                )
                or lowered
                in _TRACKING_QUERY_KEYS
            ):
                continue

            filtered_query.append(
                (key, value)
            )

        filtered_query.sort()

        scheme = (
            parsed.scheme.casefold()
        )

        netloc = (
            parsed.netloc.casefold()
        )

        path = parsed.path or "/"

        if (
            path != "/"
            and path.endswith("/")
        ):
            path = path.rstrip("/")

        return urlunsplit(
            (
                scheme,
                netloc,
                path,
                urlencode(
                    filtered_query,
                    doseq=True,
                ),
                "",
            )
        )

    except Exception:
        return url.strip()


def _normalize_notices(
    raw_notices: Any,
) -> list[str]:
    if raw_notices is None:
        return []

    if isinstance(
        raw_notices,
        str,
    ):
        raw_notices = [
            raw_notices
        ]

    if not isinstance(
        raw_notices,
        list,
    ):
        return []

    result: list[str] = []

    for item in raw_notices:
        if not isinstance(
            item,
            str,
        ):
            continue

        value = item.strip()

        if value:
            result.append(
                value
            )

    return _dedupe_strings(
        result
    )


def _clean_optional_text(
    value: Any,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return value or None


def _dedupe_strings(
    values: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def extract_evidence(
    search_result: dict[str, Any] | None,
    *,
    task_id: int,
    trace_id: str,
    query: str,
    backend: str,
) -> list[Evidence]:
    """Convert normalized search results into traceable evidence items."""

    if not search_result:
        return []

    evidence_items: list[
        Evidence
    ] = []

    results = search_result.get(
        "results",
        [],
    )

    if not isinstance(
        results,
        list,
    ):
        return []

    for rank, item in enumerate(
        results,
        start=1,
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        if not any(
            (
                item.get("title"),
                item.get("url"),
                item.get("content"),
                item.get("raw_content"),
            )
        ):
            continue

        evidence_items.append(
            Evidence(
                task_id=task_id,
                trace_id=trace_id,
                query=query,
                backend=backend,
                source_title=item.get(
                    "title"
                ),
                source_url=item.get(
                    "url"
                ),
                snippet=item.get(
                    "content"
                ),
                content=item.get(
                    "raw_content"
                ),
                source_rank=rank,
            )
        )

    return evidence_items


def prepare_research_context(
    search_result: dict[str, Any] | None,
    answer_text: Optional[str],
    config: Configuration,
) -> tuple[str, str]:
    """Build structured context and source summary for downstream agents."""

    safe_result = (
        search_result
        if isinstance(
            search_result,
            dict,
        )
        else {"results": []}
    )

    sources_summary = format_sources(
        safe_result
    )

    context = (
        deduplicate_and_format_sources(
            safe_result,
            max_tokens_per_source=(
                MAX_TOKENS_PER_SOURCE
            ),
            fetch_full_page=(
                config.fetch_full_page
            ),
        )
    )

    if answer_text:
        context = (
            f"AI直接答案：\n"
            f"{answer_text}\n\n"
            f"{context}"
        )

    return (
        sources_summary,
        context,
    )
