import pytest

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


def test_qdrant_official_documentation_is_high_authority():
    decision = DecisionCase(
        decision_id="dec_qdrant_docs",
        question="Choose vector database",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_qdrant_docs",
        query="Qdrant docs",
        backend="web",
        source_title="Qdrant Documentation",
        source_url=(
            "https://qdrant.tech/documentation/guides/"
        ),
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert (
        result.authority_type
        == "OFFICIAL_DOCUMENTATION"
    )
    assert result.authority_level == "HIGH"


def test_milvus_official_documentation_is_high_authority():
    decision = DecisionCase(
        decision_id="dec_milvus_docs",
        question="Choose vector database",
        candidates=[
            Candidate(
                candidate_id="cand_milvus",
                name="Milvus",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_milvus_docs",
        query="Milvus docs",
        backend="web",
        source_title="Milvus Documentation",
        source_url=(
            "https://milvus.io/docs/"
            "overview.md"
        ),
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert (
        result.authority_type
        == "OFFICIAL_DOCUMENTATION"
    )
    assert result.authority_level == "HIGH"


def test_weaviate_docs_subdomain_is_high_authority():
    decision = DecisionCase(
        decision_id="dec_weaviate_docs",
        question="Choose vector database",
        candidates=[
            Candidate(
                candidate_id="cand_weaviate",
                name="Weaviate",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_weaviate_docs",
        query="Weaviate docs",
        backend="web",
        source_title="Weaviate Docs",
        source_url=(
            "https://docs.weaviate.io/"
            "weaviate/configuration"
        ),
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert (
        result.authority_type
        == "OFFICIAL_DOCUMENTATION"
    )
    assert result.authority_level == "HIGH"


def test_milvus_io_github_org_matches_candidate():
    decision = DecisionCase(
        decision_id="dec_milvus_repo",
        question="Choose vector database",
        candidates=[
            Candidate(
                candidate_id="cand_milvus",
                name="Milvus",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_milvus_repo",
        query="Milvus GitHub",
        backend="web",
        source_title="Milvus source",
        source_url=(
            "https://github.com/"
            "milvus-io/milvus"
        ),
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert (
        result.authority_type
        == "SOURCE_REPOSITORY"
    )
    assert result.authority_level == "HIGH"


def test_random_github_repo_named_after_candidate_is_not_official():
    decision = DecisionCase(
        decision_id="dec_random_repo",
        question="Choose vector database",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_random_repo",
        query="Qdrant GitHub",
        backend="web",
        source_title="Qdrant fork",
        source_url=(
            "https://github.com/"
            "random-user/qdrant"
        ),
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert (
        result.authority_type
        == "INDEPENDENT_TECHNICAL"
    )
    assert result.authority_level == "MEDIUM"


def test_candidate_name_substring_in_unrelated_domain_is_not_vendor():
    decision = DecisionCase(
        decision_id="dec_false_domain",
        question="Choose database",
        candidates=[
            Candidate(
                candidate_id="cand_redis",
                name="Redis",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_false_domain",
        query="Redis",
        backend="web",
        source_title="Rediscovery database article",
        source_url=(
            "https://rediscovery.example.com/"
            "database"
        ),
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert result.authority_type != (
        "OFFICIAL_DOCUMENTATION"
    )
    assert result.authority_type != "VENDOR"


def test_vendor_home_page_is_not_mislabeled_as_documentation():
    decision = DecisionCase(
        decision_id="dec_qdrant_home",
        question="Choose vector database",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_qdrant_home",
        query="Qdrant",
        backend="web",
        source_title="Qdrant Vector Database",
        source_url="https://qdrant.tech/",
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert result.authority_type == "VENDOR"
    assert result.authority_level == "MEDIUM"


def test_vendor_blog_is_not_mislabeled_as_documentation():
    decision = DecisionCase(
        decision_id="dec_weaviate_blog",
        question="Choose vector database",
        candidates=[
            Candidate(
                candidate_id="cand_weaviate",
                name="Weaviate",
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_weaviate_blog",
        query="Weaviate scalability",
        backend="web",
        source_title="Scaling vector search",
        source_url=(
            "https://weaviate.io/blog/"
            "scaling-vector-search"
        ),
    )

    result = recognize_source_authority(
        evidence,
        decision,
    )

    assert result.authority_type == "VENDOR"
    assert result.authority_level == "MEDIUM"


def decision_for(candidate_name):
    return DecisionCase(
        decision_id="dec_official_domain",
        question=f"Should we choose {candidate_name}?",
        candidates=[
            Candidate(
                candidate_id="cand_official_domain",
                name=candidate_name,
            )
        ],
    )


@pytest.mark.parametrize(
    ("candidate_name", "url"),
    [
        ("PostgreSQL", "https://postgresql.org/docs/current/"),
        ("PostgreSQL", "https://www.postgresql.org/docs/current/"),
        ("MongoDB", "https://mongodb.com/docs/manual/"),
        ("Microsoft", "https://learn.microsoft.com/en-us/azure/"),
        ("AWS", "https://docs.aws.amazon.com/AmazonRDS/latest/"),
    ],
)
def test_known_candidate_owner_documentation_is_official(
    candidate_name,
    url,
):
    result = recognize_source_authority(
        evidence(url, title=f"{candidate_name} Documentation"),
        decision_for(candidate_name),
    )

    assert result.authority_type == "OFFICIAL_DOCUMENTATION"
    assert result.authority_level == "HIGH"
    assert any(
        signal.startswith("official_owner:")
        for signal in result.signals
    )


def test_openai_blog_is_official_vendor_but_not_postgresql_docs():
    result = recognize_source_authority(
        evidence(
            "https://openai.com/index/scaling-postgresql/",
            title="Scaling PostgreSQL",
        ),
        decision_for("PostgreSQL"),
    )

    assert result.authority_type == "VENDOR"
    assert result.authority_level == "MEDIUM"
    assert "official_owner:OpenAI" in result.signals


@pytest.mark.parametrize(
    "url",
    [
        "https://mongodb.com.evil.example/docs/",
        "https://amazon.com.fake.example/docs/",
        "https://postgresql.org.attacker.example/docs/",
    ],
)
def test_official_domain_lookalikes_are_not_vendor_sources(url):
    result = recognize_source_authority(
        evidence(url, title="Documentation"),
        decision_for("PostgreSQL"),
    )

    assert result.authority_type not in {
        "OFFICIAL_DOCUMENTATION",
        "VENDOR",
    }
