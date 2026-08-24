from models import (
    Candidate,
    DecisionCase,
    Evidence,
)
from services.source_authority import (
    authority_confidence,
    recognize_source_authority,
)


def decision():
    return DecisionCase(
        decision_id="dec_authority",
        question="Choose database",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            ),
            Candidate(
                candidate_id="cand_milvus",
                name="Milvus",
            ),
        ],
    )


def evidence(
    url,
    *,
    title="",
):
    return Evidence(
        evidence_id="evi_test",
        task_id=1,
        trace_id="trace_test",
        query="test",
        backend="web",
        source_title=title,
        source_url=url,
    )


def test_vendor_domain_is_official_documentation():
    result = recognize_source_authority(
        evidence(
            "https://qdrant.tech/documentation/",
            title="Qdrant Documentation",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "OFFICIAL_DOCUMENTATION"
    )

    assert (
        result.authority_level
        == "HIGH"
    )


def test_docs_word_on_unrelated_domain_is_not_official():
    result = recognize_source_authority(
        evidence(
            "https://example.com/docs/qdrant",
            title="Qdrant Documentation Guide",
        ),
        decision(),
    )

    assert (
        result.authority_type
        != "OFFICIAL_DOCUMENTATION"
    )


def test_official_security_surface():
    result = recognize_source_authority(
        evidence(
            "https://qdrant.tech/security/",
            title="Qdrant Security",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "OFFICIAL_SECURITY"
    )


def test_official_pricing_surface():
    result = recognize_source_authority(
        evidence(
            "https://qdrant.tech/pricing/",
            title="Qdrant Pricing",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "OFFICIAL_PRICING"
    )


def test_candidate_github_repository():
    result = recognize_source_authority(
        evidence(
            "https://github.com/qdrant/qdrant",
            title="Qdrant repository",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "SOURCE_REPOSITORY"
    )

    assert (
        result.authority_level
        == "HIGH"
    )


def test_candidate_github_issue_is_not_repository_authority():
    result = recognize_source_authority(
        evidence(
            (
                "https://github.com/"
                "qdrant/qdrant/issues/123"
            ),
            title="Issue 123",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "ISSUE_TRACKER"
    )

    assert (
        result.authority_level
        == "MEDIUM"
    )


def test_unrelated_github_repo_is_not_candidate_official():
    result = recognize_source_authority(
        evidence(
            "https://github.com/random/example",
            title="Qdrant benchmark",
        ),
        decision(),
    )

    assert (
        result.authority_type
        != "SOURCE_REPOSITORY"
    )


def test_arxiv_is_academic():
    result = recognize_source_authority(
        evidence(
            "https://arxiv.org/abs/2401.12345",
            title="Vector Search Study",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "ACADEMIC"
    )

    assert (
        result.authority_level
        == "HIGH"
    )


def test_reddit_is_community():
    result = recognize_source_authority(
        evidence(
            "https://reddit.com/r/vectordatabase/comments/x",
            title="Qdrant experience",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "COMMUNITY"
    )

    assert (
        result.authority_level
        == "LOW"
    )


def test_independent_benchmark():
    result = recognize_source_authority(
        evidence(
            "https://example.com/vector-benchmark",
            title="Vector database benchmark",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "INDEPENDENT_BENCHMARK"
    )


def test_unknown_source_stays_unknown():
    result = recognize_source_authority(
        evidence(
            "https://example.com/article",
            title="An article",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "UNKNOWN"
    )

    assert (
        result.authority_level
        == "UNKNOWN"
    )


def test_missing_url_stays_unknown():
    result = recognize_source_authority(
        evidence(
            None,
            title="Qdrant Documentation",
        ),
        decision(),
    )

    assert (
        result.authority_type
        == "UNKNOWN"
    )


def test_search_query_does_not_self_certify_authority():
    item = evidence(
        "https://example.com/article",
        title="Comparison",
    )

    item.query = (
        "Qdrant official documentation"
    )

    result = recognize_source_authority(
        item,
        decision(),
    )

    assert (
        result.authority_type
        != "OFFICIAL_DOCUMENTATION"
    )


def test_unknown_authority_never_upgrades_legacy_confidence():
    result = recognize_source_authority(
        evidence(
            "https://example.com/article",
        ),
        decision(),
    )

    confidence = authority_confidence(
        result,
        legacy_confidence=0.9,
    )

    assert confidence <= 0.5


def test_recognition_is_deterministic():
    item = evidence(
        "https://qdrant.tech/documentation/",
        title="Qdrant Documentation",
    )

    first = recognize_source_authority(
        item,
        decision(),
    )

    second = recognize_source_authority(
        item,
        decision(),
    )

    assert first == second
