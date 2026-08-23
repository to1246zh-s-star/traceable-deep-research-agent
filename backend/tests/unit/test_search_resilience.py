from copy import deepcopy

from config import Configuration
from services import search
from services.search import (
    dispatch_search,
    extract_evidence,
    normalize_search_payload,
)


def config():
    return Configuration(
        fetch_full_page=False,
    )


def test_provider_exception_degrades_without_raising(
    monkeypatch,
):
    def fail(_payload):
        raise TimeoutError(
            "provider timeout"
        )

    monkeypatch.setattr(
        search._GLOBAL_SEARCH_TOOL,
        "run",
        fail,
    )

    (
        payload,
        notices,
        answer,
        backend,
    ) = dispatch_search(
        "vector database",
        config(),
        0,
    )

    assert payload is not None
    assert payload["results"] == []
    assert payload["degraded"] is True
    assert payload["error_type"] == (
        "TimeoutError"
    )

    assert notices
    assert answer is None
    assert backend


def test_provider_text_notice_becomes_degraded_empty_result(
    monkeypatch,
):
    monkeypatch.setattr(
        search._GLOBAL_SEARCH_TOOL,
        "run",
        lambda _payload: (
            "Search temporarily unavailable"
        ),
    )

    payload, notices, answer, _ = (
        dispatch_search(
            "query",
            config(),
            0,
        )
    )

    assert payload["results"] == []
    assert payload["degraded"] is True
    assert notices == [
        "Search temporarily unavailable"
    ]
    assert answer is None


def test_malformed_top_level_payload_is_graceful():
    payload = normalize_search_payload(
        ["not", "a", "mapping"],
        search_api="tavily",
    )

    assert payload["results"] == []
    assert payload["degraded"] is True
    assert payload["error_type"] == (
        "malformed_payload"
    )


def test_partial_valid_results_are_preserved():
    payload = normalize_search_payload(
        {
            "backend": "tavily",
            "results": [
                {
                    "title": "Valid A",
                    "url": "https://example.com/a",
                    "content": "A",
                },
                "bad item",
                {},
                {
                    "title": "Valid B",
                    "url": "https://example.com/b",
                    "content": "B",
                },
            ],
        },
        search_api="tavily",
    )

    assert [
        item["title"]
        for item in payload["results"]
    ] == [
        "Valid A",
        "Valid B",
    ]

    assert payload["degraded"] is True

    assert any(
        "malformed" in notice.lower()
        for notice in payload["notices"]
    )


def test_tracking_url_duplicates_are_removed():
    payload = normalize_search_payload(
        {
            "results": [
                {
                    "title": "First",
                    "url": (
                        "https://example.com/docs"
                        "?utm_source=test&id=7"
                    ),
                    "content": "first",
                },
                {
                    "title": "Duplicate",
                    "url": (
                        "https://EXAMPLE.com/docs"
                        "?id=7&utm_medium=email#top"
                    ),
                    "content": "duplicate",
                },
            ],
        },
        search_api="tavily",
    )

    assert len(
        payload["results"]
    ) == 1

    assert (
        payload["results"][0]["title"]
        == "First"
    )

    assert any(
        "duplicate" in notice.lower()
        for notice in payload["notices"]
    )


def test_duplicate_content_without_url_is_removed():
    payload = normalize_search_payload(
        {
            "results": [
                {
                    "title": "Same",
                    "content": (
                        "same content"
                    ),
                },
                {
                    "title": "Same",
                    "content": (
                        "same   content"
                    ),
                },
            ],
        },
        search_api="tavily",
    )

    assert len(
        payload["results"]
    ) == 1


def test_empty_search_is_not_negative_or_degraded():
    payload = normalize_search_payload(
        {
            "backend": "tavily",
            "results": [],
            "answer": None,
        },
        search_api="tavily",
    )

    assert payload["results"] == []
    assert payload["degraded"] is False

    assert not any(
        "negative" in notice.lower()
        for notice in payload["notices"]
    )


def test_non_list_results_are_filtered_gracefully():
    payload = normalize_search_payload(
        {
            "results": {
                "unexpected": "mapping"
            },
        },
        search_api="tavily",
    )

    assert payload["results"] == []
    assert payload["degraded"] is True


def test_normalization_does_not_mutate_provider_payload():
    raw = {
        "backend": "tavily",
        "results": [
            {
                "title": "Example",
                "url": (
                    "https://example.com/"
                    "?utm_source=x"
                ),
                "content": "content",
            }
        ],
    }

    before = deepcopy(raw)

    normalize_search_payload(
        raw,
        search_api="tavily",
    )

    assert raw == before


def test_evidence_preserves_only_valid_partial_results():
    payload = normalize_search_payload(
        {
            "results": [
                {
                    "title": "A",
                    "url": "https://example.com/a",
                    "content": "snippet A",
                    "raw_content": "full A",
                },
                {},
                {
                    "title": "B",
                    "url": "https://example.com/b",
                    "content": "snippet B",
                },
            ]
        },
        search_api="tavily",
    )

    evidence = extract_evidence(
        payload,
        task_id=1,
        trace_id="trace_test",
        query="test",
        backend="tavily",
    )

    assert len(evidence) == 2

    assert [
        item.source_rank
        for item in evidence
    ] == [
        1,
        2,
    ]

    assert [
        item.source_title
        for item in evidence
    ] == [
        "A",
        "B",
    ]
