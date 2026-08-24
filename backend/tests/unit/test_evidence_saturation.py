from models import (
    AdaptiveResearchIteration,
    Evidence,
)
from services.evidence_saturation import (
    EvidenceSaturationSnapshot,
    assess_iteration_evidence_saturation,
    canonicalize_url,
    enrich_retrieval_yield_with_saturation,
    jaccard_similarity,
)


def evidence(
    evidence_id,
    *,
    url,
    content,
    title="Example",
):
    return Evidence(
        evidence_id=evidence_id,
        task_id=1,
        trace_id="trace",
        query="test",
        backend="web",
        source_title=title,
        source_url=url,
        snippet=content,
    )


def iteration(
    *,
    status="completed",
):
    return AdaptiveResearchIteration(
        decision_id="dec_test",
        iteration_number=1,
        status=status,
    )


def snap(
    items=None,
):
    return EvidenceSaturationSnapshot(
        evidence_items=(
            items
            or []
        )
    )


def test_tracking_parameters_do_not_create_new_url():
    first = canonicalize_url(
        "https://example.com/docs?q=1&utm_source=x"
    )

    second = canonicalize_url(
        "https://www.example.com/docs?q=1"
    )

    assert first == second


def test_jaccard_identical_content_is_one():
    tokens = {
        "qdrant",
        "scalability",
        "benchmark",
    }

    assert (
        jaccard_similarity(
            tokens,
            tokens,
        )
        == 1.0
    )


def test_no_new_evidence_is_unknown():
    item = iteration()

    old = evidence(
        "e1",
        url="https://example.com/a",
        content="Qdrant scalability benchmark results",
    )

    status = assess_iteration_evidence_saturation(
        item,
        snap([old]),
        snap([old]),
    )

    assert status == "UNKNOWN"


def test_failed_iteration_is_unknown():
    item = iteration(
        status="failed",
    )

    status = assess_iteration_evidence_saturation(
        item,
        snap(),
        snap(),
    )

    assert status == "UNKNOWN"


def test_distinct_sources_and_content_are_low_saturation():
    item = iteration()

    old = evidence(
        "e1",
        url="https://vendor-a.com/docs",
        content=(
            "Official installation and deployment instructions."
        ),
    )

    new_a = evidence(
        "e2",
        url="https://benchmark-lab.com/result",
        content=(
            "Independent latency throughput benchmark "
            "across several workload sizes."
        ),
    )

    new_b = evidence(
        "e3",
        url="https://arxiv.org/abs/123",
        content=(
            "Academic study of vector indexing "
            "under distributed workloads."
        ),
    )

    status = assess_iteration_evidence_saturation(
        item,
        snap([old]),
        snap([
            old,
            new_a,
            new_b,
        ]),
    )

    assert status == "LOW_SATURATION"
    assert item.novel_content_count == 2
    assert item.new_unique_source_count == 2


def test_same_domain_can_raise_moderate_saturation():
    item = iteration()

    old = evidence(
        "e1",
        url="https://example.com/docs/a",
        content=(
            "Installation guide for cluster deployment."
        ),
    )

    distinct_contents = [
        (
            "Authentication encryption authorization "
            "and identity provider configuration."
        ),
        (
            "Distributed shard replication topology "
            "and horizontal scaling configuration."
        ),
        (
            "Backup restore snapshot retention "
            "and disaster recovery procedures."
        ),
        (
            "Monitoring metrics alerting observability "
            "and production diagnostics guidance."
        ),
    ]

    new_items = [
        evidence(
            f"e{i}",
            url=f"https://example.com/docs/{i}",
            content=content,
        )
        for i, content in enumerate(
            distinct_contents,
            start=2,
        )
    ]

    status = assess_iteration_evidence_saturation(
        item,
        snap([old]),
        snap([
            old,
            *new_items,
        ]),
    )

    assert (
        item.duplicate_domain_ratio
        == 1.0
    )

    assert status == "MODERATE_SATURATION"


def test_near_duplicate_content_is_high_saturation():
    item = iteration()

    base = (
        "Qdrant distributed scalability benchmark "
        "shows latency throughput performance "
        "under concurrent vector search workload"
    )

    old = evidence(
        "e1",
        url="https://example.com/a",
        content=base,
    )

    new_items = [
        evidence(
            "e2",
            url="https://mirror-a.com/a",
            content=base,
        ),
        evidence(
            "e3",
            url="https://mirror-b.com/a",
            content=base,
        ),
    ]

    status = assess_iteration_evidence_saturation(
        item,
        snap([old]),
        snap([
            old,
            *new_items,
        ]),
    )

    assert status == "HIGH_SATURATION"

    assert (
        item.near_duplicate_content_ratio
        == 1.0
    )

    assert item.novel_content_count == 0


def test_duplicates_inside_same_new_batch_are_detected():
    item = iteration()

    content = (
        "Independent benchmark compares "
        "latency throughput and memory usage."
    )

    first = evidence(
        "e1",
        url="https://a.example/test",
        content=content,
    )

    second = evidence(
        "e2",
        url="https://b.example/test",
        content=content,
    )

    status = assess_iteration_evidence_saturation(
        item,
        snap(),
        snap([
            first,
            second,
        ]),
    )

    assert status == "MODERATE_SATURATION"

    assert (
        item.near_duplicate_content_ratio
        == 0.5
    )


def test_high_domain_repetition_alone_does_not_force_high():
    item = iteration()

    old = evidence(
        "e0",
        url="https://docs.example.com/start",
        content="Initial deployment instructions",
    )

    first = evidence(
        "e1",
        url="https://docs.example.com/security",
        content=(
            "Authentication encryption authorization "
            "and security configuration guidance"
        ),
    )

    second = evidence(
        "e2",
        url="https://docs.example.com/scaling",
        content=(
            "Shard replication scaling topology "
            "and distributed workload guidance"
        ),
    )

    status = assess_iteration_evidence_saturation(
        item,
        snap([old]),
        snap([
            old,
            first,
            second,
        ]),
    )

    assert status == "MODERATE_SATURATION"

    assert (
        item.near_duplicate_content_ratio
        < 0.60
    )


def test_saturation_enriches_yield_reason_without_changing_yield():
    item = iteration()

    item.retrieval_yield_status = (
        "LOW_YIELD"
    )

    item.retrieval_yield_reasons = [
        "2 new evidence item(s)"
    ]

    item.evidence_saturation_status = (
        "HIGH_SATURATION"
    )

    enrich_retrieval_yield_with_saturation(
        item
    )

    assert (
        item.retrieval_yield_status
        == "LOW_YIELD"
    )

    assert (
        "evidence saturation: high_saturation"
        in item.retrieval_yield_reasons
    )


def test_saturation_assessment_is_deterministic():
    before = snap()

    after = snap([
        evidence(
            "e1",
            url="https://a.example/x",
            content="Independent benchmark latency throughput",
        ),
        evidence(
            "e2",
            url="https://b.example/y",
            content="Independent benchmark latency throughput",
        ),
    ])

    first = iteration()
    second = iteration()

    assert (
        assess_iteration_evidence_saturation(
            first,
            before,
            after,
        )
        == assess_iteration_evidence_saturation(
            second,
            before,
            after,
        )
    )

    assert (
        first.near_duplicate_content_ratio
        == second.near_duplicate_content_ratio
    )


def test_identical_body_with_different_titles_is_near_duplicate():
    item = iteration()

    body = (
        "Independent benchmark measures latency "
        "throughput memory and concurrent vector search."
    )

    old = evidence(
        "e1",
        url="https://original.example/report",
        title="Original engineering report",
        content=body,
    )

    mirrored = evidence(
        "e2",
        url="https://mirror.example/report",
        title="Completely different article title",
        content=body,
    )

    status = assess_iteration_evidence_saturation(
        item,
        snap([old]),
        snap([
            old,
            mirrored,
        ]),
    )

    assert (
        item.near_duplicate_content_ratio
        == 1.0
    )

    assert status == "HIGH_SATURATION"


def test_title_is_used_when_body_is_missing():
    from services.evidence_saturation import (
        evidence_tokens,
    )

    item = Evidence(
        evidence_id="e_title",
        task_id=1,
        trace_id="trace",
        query="test",
        backend="web",
        source_title=(
            "Qdrant Distributed Scalability Benchmark"
        ),
        source_url="https://example.com",
        snippet=None,
        content=None,
    )

    tokens = evidence_tokens(
        item
    )

    assert "qdrant" in tokens
    assert "distributed" in tokens
    assert "scalability" in tokens
    assert "benchmark" in tokens
