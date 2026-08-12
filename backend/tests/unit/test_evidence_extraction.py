from services.search import extract_evidence


def test_extract_evidence_maps_structured_search_results():
    search_result = {
        "results": [
            {
                "title": "Source A",
                "url": "https://example.com/a",
                "content": "Search summary A",
                "raw_content": "Full page A",
            },
            {
                "title": "Source B",
                "url": "https://example.com/b",
                "content": "Search summary B",
                "raw_content": "Full page B",
            },
        ]
    }

    evidence = extract_evidence(
        search_result,
        task_id=3,
        trace_id="trace_abc",
        query="example query",
        backend="tavily",
    )

    assert len(evidence) == 2

    first = evidence[0]

    assert first.task_id == 3
    assert first.trace_id == "trace_abc"
    assert first.query == "example query"
    assert first.backend == "tavily"

    assert first.source_title == "Source A"
    assert first.source_url == "https://example.com/a"
    assert first.snippet == "Search summary A"
    assert first.content == "Full page A"
    assert first.source_rank == 1

    assert evidence[1].source_rank == 2


def test_extract_evidence_returns_empty_list_without_results():
    assert (
        extract_evidence(
            None,
            task_id=1,
            trace_id="trace_empty",
            query="query",
            backend="tavily",
        )
        == []
    )

    assert (
        extract_evidence(
            {"results": []},
            task_id=1,
            trace_id="trace_empty",
            query="query",
            backend="tavily",
        )
        == []
    )
