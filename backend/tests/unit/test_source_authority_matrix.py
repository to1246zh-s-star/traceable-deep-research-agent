import pytest

from models import Candidate, DecisionCase, Evidence
from services.source_authority import (
    recognize_source_authority,
)
from services.source_strategy_match import (
    AUTHORITY_TO_SOURCE_TYPES,
)


@pytest.mark.parametrize(
    (
        "label",
        "candidate_name",
        "title",
        "url",
        "expected_type",
        "expected_level",
        "expected_strategy_type",
    ),
    [
        # Qdrant
        (
            "Qdrant docs",
            "Qdrant",
            "Qdrant Documentation",
            "https://qdrant.tech/documentation/",
            "OFFICIAL_DOCUMENTATION",
            "HIGH",
            "official_documentation",
        ),
        (
            "Qdrant GitHub",
            "Qdrant",
            "Qdrant source repository",
            "https://github.com/qdrant/qdrant",
            "SOURCE_REPOSITORY",
            "HIGH",
            "source_repository",
        ),
        (
            "Qdrant issue",
            "Qdrant",
            "Qdrant issue",
            "https://github.com/qdrant/qdrant/issues/1",
            "ISSUE_TRACKER",
            "MEDIUM",
            "issue_tracker",
        ),
        (
            "Qdrant homepage",
            "Qdrant",
            "Qdrant Vector Database",
            "https://qdrant.tech/",
            "VENDOR",
            "MEDIUM",
            None,
        ),
        (
            "Qdrant blog",
            "Qdrant",
            "Qdrant engineering blog",
            "https://qdrant.tech/articles/vector-search/",
            "VENDOR",
            "MEDIUM",
            None,
        ),

        # Milvus
        (
            "Milvus docs",
            "Milvus",
            "Milvus Documentation",
            "https://milvus.io/docs/overview.md",
            "OFFICIAL_DOCUMENTATION",
            "HIGH",
            "official_documentation",
        ),
        (
            "Milvus GitHub",
            "Milvus",
            "Milvus source repository",
            "https://github.com/milvus-io/milvus",
            "SOURCE_REPOSITORY",
            "HIGH",
            "source_repository",
        ),
        (
            "Milvus issue",
            "Milvus",
            "Milvus issue",
            "https://github.com/milvus-io/milvus/issues/1",
            "ISSUE_TRACKER",
            "MEDIUM",
            "issue_tracker",
        ),
        (
            "Milvus homepage",
            "Milvus",
            "Milvus Vector Database",
            "https://milvus.io/",
            "VENDOR",
            "MEDIUM",
            None,
        ),

        # Weaviate
        (
            "Weaviate docs",
            "Weaviate",
            "Weaviate Docs",
            "https://docs.weaviate.io/weaviate/configuration",
            "OFFICIAL_DOCUMENTATION",
            "HIGH",
            "official_documentation",
        ),
        (
            "Weaviate GitHub",
            "Weaviate",
            "Weaviate source repository",
            "https://github.com/weaviate/weaviate",
            "SOURCE_REPOSITORY",
            "HIGH",
            "source_repository",
        ),
        (
            "Weaviate issue",
            "Weaviate",
            "Weaviate issue",
            "https://github.com/weaviate/weaviate/issues/1",
            "ISSUE_TRACKER",
            "MEDIUM",
            "issue_tracker",
        ),
        (
            "Weaviate homepage",
            "Weaviate",
            "Weaviate Vector Database",
            "https://weaviate.io/",
            "VENDOR",
            "MEDIUM",
            None,
        ),

        # False positives
        (
            "Random Qdrant repo",
            "Qdrant",
            "Qdrant fork",
            "https://github.com/random-user/qdrant",
            "INDEPENDENT_TECHNICAL",
            "MEDIUM",
            "independent_source",
        ),
        (
            "Random Milvus repo",
            "Milvus",
            "Milvus fork",
            "https://github.com/random-user/milvus",
            "INDEPENDENT_TECHNICAL",
            "MEDIUM",
            "independent_source",
        ),
        (
            "Unrelated Qdrant-like domain",
            "Qdrant",
            "Qdrant article",
            "https://qdrant-review.example.com/article",
            "UNKNOWN",
            "UNKNOWN",
            None,
        ),
    ],
)
def test_real_world_source_authority_matrix(
    label,
    candidate_name,
    title,
    url,
    expected_type,
    expected_level,
    expected_strategy_type,
):
    decision = DecisionCase(
        decision_id=(
            "dec_"
            + candidate_name.casefold()
        ),
        question=(
            f"Should we choose {candidate_name}?"
        ),
        candidates=[
            Candidate(
                candidate_id=(
                    "cand_"
                    + candidate_name.casefold()
                ),
                name=candidate_name,
            )
        ],
    )

    evidence = Evidence(
        task_id=1,
        trace_id="trace_matrix",
        query=label,
        backend="matrix",
        source_title=title,
        source_url=url,
    )

    authority = recognize_source_authority(
        evidence,
        decision,
    )

    assert authority.authority_type == (
        expected_type
    )
    assert authority.authority_level == (
        expected_level
    )

    strategy_types = (
        AUTHORITY_TO_SOURCE_TYPES.get(
            authority.authority_type,
            set(),
        )
    )

    if expected_strategy_type is None:
        assert not strategy_types
    else:
        assert (
            expected_strategy_type
            in strategy_types
        )


def test_vendor_surface_does_not_satisfy_official_docs_strategy():
    assert "VENDOR" not in (
        AUTHORITY_TO_SOURCE_TYPES
    )


def test_unknown_authority_does_not_satisfy_any_strategy():
    assert "UNKNOWN" not in (
        AUTHORITY_TO_SOURCE_TYPES
    )
