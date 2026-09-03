from models import (
    Candidate,
    DecisionCase,
    DecisionCriterion,
    ResearchGap,
)
from services.search_strategy import (
    assign_search_strategies,
    build_strategy_query,
    classify_search_strategy,
)


def decision():
    return DecisionCase(
        decision_id="dec_strategy",
        question="Choose database",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="Qdrant",
            ),
            Candidate(
                candidate_id="cand_b",
                name="Milvus",
            ),
        ],
        criteria=[
            DecisionCriterion(
                criterion_id="crit_scale",
                name="Scalability",
                weight=0.25,
            ),
            DecisionCriterion(
                criterion_id="crit_security",
                name="Security compliance",
                weight=0.20,
            ),
            DecisionCriterion(
                criterion_id="crit_migration",
                name="Migration complexity",
                weight=0.20,
            ),
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operational reliability",
                weight=0.20,
            ),
            DecisionCriterion(
                criterion_id="crit_cost",
                name="Cost",
                weight=0.15,
            ),
        ],
    )


def gap(
    criterion_id,
    *,
    query="Qdrant evidence",
):
    return ResearchGap(
        gap_id=f"gap_{criterion_id}",
        candidate_id="cand_a",
        criterion_id=criterion_id,
        gap_type="low_coverage",
        severity=0.8,
        description="Need stronger evidence",
        suggested_query=query,
    )


def test_scalability_uses_performance_strategy():
    item = gap(
        "crit_scale"
    )

    assign_search_strategies(
        decision(),
        [item],
    )

    assert (
        item.search_strategy
        == "PERFORMANCE_SCALE"
    )

    assert item.preferred_source_types == [
        "official_documentation"
    ]


def test_security_uses_security_strategy():
    item = gap(
        "crit_security"
    )

    assign_search_strategies(
        decision(),
        [item],
    )

    assert (
        item.search_strategy
        == "SECURITY_GOVERNANCE"
    )

    assert (
        "security_advisory"
        in item.preferred_source_types
    )

    assert (
        "CVE"
        in item.suggested_query
    )


def test_migration_uses_migration_strategy():
    item = gap(
        "crit_migration"
    )

    assign_search_strategies(
        decision(),
        [item],
    )

    assert (
        item.search_strategy
        == "MIGRATION_INTEGRATION"
    )

    assert (
        "migration_guide"
        in item.preferred_source_types
    )


def test_operations_uses_reliability_strategy():
    item = gap(
        "crit_ops"
    )

    assign_search_strategies(
        decision(),
        [item],
    )

    assert (
        item.search_strategy
        == "OPERATIONS_RELIABILITY"
    )

    assert (
        "issue_tracker"
        in item.preferred_source_types
    )


def test_cost_uses_economics_strategy():
    item = gap(
        "crit_cost"
    )

    assign_search_strategies(
        decision(),
        [item],
    )

    assert (
        item.search_strategy
        == "COST_ECONOMICS"
    )

    assert (
        "official_pricing_documentation"
        in item.preferred_source_types
    )


def test_unknown_named_criterion_uses_general_technical():
    strategy = classify_search_strategy(
        criterion_name="Developer experience",
        gap_type="low_coverage",
        description="Need evidence",
    )

    assert strategy == (
        "GENERAL_TECHNICAL"
    )


def test_no_semantic_context_uses_general():
    strategy = classify_search_strategy(
        criterion_name="",
        gap_type="missing",
        description="",
    )

    assert strategy == "GENERAL"


def test_existing_query_is_preserved():
    item = gap(
        "crit_scale",
        query=(
            "Qdrant scalability "
            "independent verification"
        ),
    )

    assign_search_strategies(
        decision(),
        [item],
    )

    assert item.suggested_query.startswith(
        "Qdrant scalability "
        "independent verification"
    )


def test_strategy_query_does_not_invent_candidate_facts():
    item = gap(
        "crit_security",
        query="Qdrant security",
    )

    assign_search_strategies(
        decision(),
        [item],
    )

    query = item.suggested_query.lower()

    assert "qdrant security" in query

    # Strategy asks for evidence; it does not assert an outcome.
    assert "secure" not in query
    assert "compliant" not in query


def test_assignment_mutates_only_retrieval_fields():
    item = gap(
        "crit_scale"
    )

    original_priority = item.priority
    original_impact = item.decision_impact
    original_status = item.status

    assign_search_strategies(
        decision(),
        [item],
    )

    assert (
        item.priority
        == original_priority
    )

    assert (
        item.decision_impact
        == original_impact
    )

    assert (
        item.status
        == original_status
    )


def test_assignment_is_deterministic():
    first = gap(
        "crit_scale"
    )

    second = gap(
        "crit_scale"
    )

    assign_search_strategies(
        decision(),
        [first],
    )

    assign_search_strategies(
        decision(),
        [second],
    )

    assert (
        first.search_strategy
        == second.search_strategy
    )

    assert (
        first.preferred_source_types
        == second.preferred_source_types
    )

    assert (
        first.query_qualifiers
        == second.query_qualifiers
    )

    assert (
        first.suggested_query
        == second.suggested_query
    )


def test_context_dimensions_can_drive_strategy():
    item = gap(
        "unknown_criterion"
    )

    item.context_dimensions = [
        "security",
        "compliance",
    ]

    assign_search_strategies(
        decision(),
        [item],
    )

    assert (
        item.search_strategy
        == "SECURITY_GOVERNANCE"
    )


def test_build_strategy_query_deduplicates_exact_qualifiers():
    item = gap(
        "crit_scale",
        query="official documentation",
    )

    item.query_qualifiers = [
        "official documentation",
        "benchmark",
    ]

    query = build_strategy_query(
        item,
        candidate_name="Qdrant",
        criterion_name="Scalability",
    )

    assert (
        query.casefold().count(
            "official documentation"
        )
        == 1
    )
