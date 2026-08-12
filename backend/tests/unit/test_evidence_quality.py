import pytest

from models import (
    DecisionCase,
    DecisionCriterion,
    Evidence,
    Requirement,
)
from services.evidence_quality import (
    assess_applicability,
    assess_evidence,
    assess_evidence_quality,
    assess_source_quality,
    calculate_source_diversity,
    classify_source_type,
)


def make_evidence(
    *,
    title="Qdrant Documentation",
    url="https://qdrant.tech/documentation/guides/",
    snippet="Qdrant supports production vector search.",
    content="Qdrant documentation describing production vector search.",
):
    return Evidence(
        task_id=1,
        trace_id="trace_test",
        query="vector database",
        backend="test",
        source_title=title,
        source_url=url,
        snippet=snippet,
        content=content,
    )


def test_official_documentation_classification():
    evidence = make_evidence()

    assert classify_source_type(evidence) == "official_docs"

    quality = assess_source_quality(evidence)

    assert quality.source_type == "official_docs"
    assert quality.confidence == pytest.approx(0.95)


def test_research_paper_classification():
    evidence = make_evidence(
        title="Vector Search Research",
        url="https://arxiv.org/abs/1234.5678",
    )

    assert classify_source_type(evidence) == "research_paper"


def test_community_source_classification():
    evidence = make_evidence(
        title="Qdrant experience",
        url="https://www.reddit.com/r/vectorsearch/example",
    )

    assert classify_source_type(evidence) == "community"


def test_evidence_quality_rewards_complete_content():
    complete = make_evidence(
        content="x" * 600,
    )

    incomplete = Evidence(
        task_id=1,
        trace_id="trace_test",
        query="vector database",
        backend="test",
        snippet="short",
    )

    complete_quality = assess_evidence_quality(complete)
    incomplete_quality = assess_evidence_quality(incomplete)

    assert complete_quality.completeness == pytest.approx(1.0)

    assert (
        complete_quality.quality_score
        > incomplete_quality.quality_score
    )


def test_applicability_increases_when_evidence_matches_context():
    decision = DecisionCase(
        question="Which vector database should we use?",
        context="Kubernetes production RAG system",
        requirements=[
            Requirement(
                text="Minimize operational complexity"
            )
        ],
        criteria=[
            DecisionCriterion(
                name="Reliability",
                weight=1,
            )
        ],
    )

    matching = make_evidence(
        snippet=(
            "Production Kubernetes deployment for vector database "
            "reliability and operational simplicity."
        ),
    )

    unrelated = make_evidence(
        title="Cooking Guide",
        url="https://example.com/cooking",
        snippet="Recipe for pasta and tomato sauce.",
        content="Cooking instructions.",
    )

    matching_result = assess_applicability(
        matching,
        decision,
    )

    unrelated_result = assess_applicability(
        unrelated,
        decision,
    )

    assert (
        matching_result.applicability_score
        > unrelated_result.applicability_score
    )


def test_combined_evidence_assessment():
    decision = DecisionCase(
        question="Which vector database should we use?",
        context="Production Kubernetes vector search",
    )

    evidence = make_evidence(
        content=(
            "Production Kubernetes vector search deployment "
            + "x" * 600
        ),
    )

    assessment = assess_evidence(
        evidence,
        decision,
    )

    assert assessment.evidence_id == evidence.evidence_id
    assert assessment.decision_id == decision.decision_id

    assert 0.0 <= assessment.overall_score <= 1.0

    expected = (
        assessment.source_quality.confidence
        * assessment.evidence_quality.quality_score
        * assessment.applicability.applicability_score
    )

    assert assessment.overall_score == pytest.approx(expected)


def test_source_diversity_detects_multiple_source_types():
    evidence_items = [
        make_evidence(),
        make_evidence(
            title="Vector Search Paper",
            url="https://arxiv.org/abs/1234.5678",
        ),
        make_evidence(
            title="Community discussion",
            url="https://www.reddit.com/r/vectorsearch/example",
        ),
    ]

    diversity = calculate_source_diversity(evidence_items)

    assert diversity.evidence_count == 3
    assert diversity.source_type_count == 3

    assert set(diversity.source_types) == {
        "official_docs",
        "research_paper",
        "community",
    }

    assert diversity.diversity_score == pytest.approx(1.0)


def test_source_diversity_is_lower_for_repeated_source_type():
    evidence_items = [
        make_evidence(
            url="https://vendor-a.com/docs/guide",
        ),
        make_evidence(
            url="https://vendor-b.com/docs/reference",
        ),
        make_evidence(
            url="https://vendor-c.com/docs/setup",
        ),
    ]

    diversity = calculate_source_diversity(evidence_items)

    assert diversity.evidence_count == 3
    assert diversity.source_type_count == 1

    assert diversity.diversity_score == pytest.approx(
        1 / 3
    )


def test_empty_source_diversity():
    diversity = calculate_source_diversity([])

    assert diversity.evidence_count == 0
    assert diversity.source_type_count == 0
    assert diversity.diversity_score == 0.0
    assert diversity.source_types == []
