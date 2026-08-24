from models import (
    AdaptiveResearchIteration,
    AdaptiveResearchState,
    ResearchAnalysis,
    ResearchGap,
)
from services.adaptive_research import (
    create_followup_tasks,
    record_iteration_started,
    select_research_gaps,
)
from services.strategy_replanning import (
    build_effective_followup_query,
    is_strategy_reroute,
)


def gap(
    *,
    gap_id="gap_scale",
    match_status="UNKNOWN",
    preferred=None,
    missing=None,
):
    return ResearchGap(
        gap_id=gap_id,
        candidate_id="cand_qdrant",
        criterion_id="crit_scale",
        gap_type="low_coverage",
        severity=0.8,
        description=(
            "Need stronger scalability evidence"
        ),
        suggested_query=(
            "Qdrant scalability "
            "independent verification "
            "official documentation "
            "benchmark performance"
        ),
        search_strategy=(
            "PERFORMANCE_SCALE"
        ),
        preferred_source_types=(
            preferred
            if preferred is not None
            else [
                "official_documentation",
                "benchmark",
                "academic_paper",
            ]
        ),
        query_qualifiers=[
            "official documentation",
            "benchmark",
            "performance",
        ],
        strategy_match_status=(
            match_status
        ),
        missing_source_types=(
            missing
            if missing is not None
            else []
        ),
    )


def analysis_with(
    item,
):
    return ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            item
        ],
        status="gaps_detected",
    )


def adaptive_state(
    *,
    executed_gap_ids=None,
    executed_queries=None,
):
    return AdaptiveResearchState(
        decision_id="dec_test",
        executed_gap_ids=(
            executed_gap_ids
            or []
        ),
        executed_queries=(
            executed_queries
            or []
        ),
    )


def test_full_strategy_match_has_no_followup_query():
    item = gap(
        match_status="FULL",
        missing=[],
    )

    assert (
        build_effective_followup_query(
            item
        )
        is None
    )


def test_full_strategy_match_is_not_selected():
    item = gap(
        match_status="FULL",
    )

    selected = select_research_gaps(
        analysis_with(item),
        adaptive_state(),
    )

    assert selected == []


def test_partial_targets_only_missing_sources():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
            "academic_paper",
        ],
    )

    query = (
        build_effective_followup_query(
            item
        )
    )

    assert query is not None

    assert (
        "independent benchmark"
        in query
    )

    assert (
        "academic paper"
        in query
    )

    # Already satisfied official docs should not be requested again.
    assert (
        "official documentation"
        not in query
    )


def test_none_targets_all_missing_sources():
    item = gap(
        match_status="NONE",
        missing=[
            "official_documentation",
            "benchmark",
            "academic_paper",
        ],
    )

    query = (
        build_effective_followup_query(
            item
        )
    )

    assert query is not None
    assert (
        "official documentation"
        in query
    )
    assert (
        "independent benchmark"
        in query
    )
    assert (
        "academic paper"
        in query
    )


def test_unknown_preserves_existing_query():
    item = gap(
        match_status="UNKNOWN",
    )

    assert (
        build_effective_followup_query(
            item
        )
        == item.suggested_query
    )


def test_partial_gap_is_strategy_reroute():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
        ],
    )

    assert (
        is_strategy_reroute(item)
        is True
    )


def test_unknown_gap_is_not_strategy_reroute():
    item = gap(
        match_status="UNKNOWN",
    )

    assert (
        is_strategy_reroute(item)
        is False
    )


def test_previously_executed_strategy_gap_can_reroute():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
        ],
    )

    selected = select_research_gaps(
        analysis_with(item),
        adaptive_state(
            executed_gap_ids=[
                item.gap_id
            ],
        ),
    )

    assert selected == [
        item
    ]


def test_legacy_executed_gap_still_skipped():
    item = ResearchGap(
        gap_id="gap_legacy",
        candidate_id="cand_a",
        criterion_id="crit_a",
        gap_type="low_coverage",
        severity=0.8,
        description="Need evidence",
        suggested_query="candidate evidence",
    )

    selected = select_research_gaps(
        analysis_with(item),
        adaptive_state(
            executed_gap_ids=[
                item.gap_id
            ],
        ),
    )

    assert selected == []


def test_executed_targeted_query_blocks_repeat():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
        ],
    )

    targeted_query = (
        build_effective_followup_query(
            item
        )
    )

    selected = select_research_gaps(
        analysis_with(item),
        adaptive_state(
            executed_gap_ids=[
                item.gap_id
            ],
            executed_queries=[
                targeted_query
            ],
        ),
    )

    assert selected == []


def test_changed_missing_sources_create_new_effective_query():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "academic_paper",
        ],
    )

    old_query = (
        "Qdrant scalability "
        "independent verification "
        "independent benchmark"
    )

    selected = select_research_gaps(
        analysis_with(item),
        adaptive_state(
            executed_gap_ids=[
                item.gap_id
            ],
            executed_queries=[
                old_query
            ],
        ),
    )

    assert selected == [
        item
    ]


def test_create_followup_task_uses_effective_query():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
        ],
    )

    tasks = create_followup_tasks(
        [item],
        starting_task_id=10,
    )

    assert len(tasks) == 1
    assert tasks[0].id == 11

    assert tasks[0].query == (
        build_effective_followup_query(
            item
        )
    )

    assert (
        "benchmark"
        in tasks[0].query
    )

    assert (
        "official documentation"
        not in tasks[0].query
    )


def test_followup_intent_exposes_missing_source_types():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
            "academic_paper",
        ],
    )

    task = create_followup_tasks(
        [item],
        starting_task_id=1,
    )[0]

    assert (
        "benchmark"
        in task.intent
    )

    assert (
        "academic_paper"
        in task.intent
    )


def test_full_gap_defensively_creates_no_task():
    item = gap(
        match_status="FULL",
    )

    tasks = create_followup_tasks(
        [item],
        starting_task_id=5,
    )

    assert tasks == []


def test_task_ids_remain_contiguous_when_non_actionable_gap_is_skipped():
    full_gap = gap(
        gap_id="gap_full",
        match_status="FULL",
    )

    partial_gap = gap(
        gap_id="gap_partial",
        match_status="PARTIAL",
        missing=[
            "benchmark",
        ],
    )

    tasks = create_followup_tasks(
        [
            full_gap,
            partial_gap,
        ],
        starting_task_id=20,
    )

    assert [
        task.id
        for task in tasks
    ] == [21]


def test_record_iteration_started_records_effective_query():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
        ],
    )

    state = adaptive_state()

    iteration = AdaptiveResearchIteration(
        decision_id="dec_test",
        iteration_number=1,
        gap_ids=[
            item.gap_id
        ],
        task_ids=[
            11
        ],
        status="planned",
    )

    record_iteration_started(
        state,
        iteration,
        [item],
    )

    assert state.executed_queries == [
        build_effective_followup_query(
            item
        )
    ]


def test_record_iteration_started_does_not_record_generic_query():
    item = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
        ],
    )

    state = adaptive_state()

    iteration = AdaptiveResearchIteration(
        decision_id="dec_test",
        iteration_number=1,
        gap_ids=[
            item.gap_id
        ],
        task_ids=[
            1
        ],
        status="planned",
    )

    record_iteration_started(
        state,
        iteration,
        [item],
    )

    assert (
        item.suggested_query
        not in state.executed_queries
    )


def test_query_generation_is_deterministic():
    first = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
            "academic_paper",
        ],
    )

    second = gap(
        match_status="PARTIAL",
        missing=[
            "benchmark",
            "academic_paper",
        ],
    )

    assert (
        build_effective_followup_query(
            first
        )
        == build_effective_followup_query(
            second
        )
    )


def test_original_criterion_term_survives_suffix_removal():
    item = ResearchGap(
        gap_id="gap_perf",
        candidate_id="cand_a",
        criterion_id="crit_perf",
        gap_type="low_coverage",
        severity=0.8,
        description="Need performance evidence",
        suggested_query=(
            "Candidate performance "
            "official documentation "
            "benchmark performance"
        ),
        search_strategy=(
            "PERFORMANCE_SCALE"
        ),
        preferred_source_types=[
            "official_documentation",
            "benchmark",
        ],
        query_qualifiers=[
            "official documentation",
            "benchmark",
            "performance",
        ],
        strategy_match_status="PARTIAL",
        missing_source_types=[
            "benchmark",
        ],
    )

    query = (
        build_effective_followup_query(
            item
        )
    )

    assert query is not None

    # The original criterion survives; only the appended suffix is stripped.
    assert query.startswith(
        "Candidate performance"
    )

    assert (
        "independent benchmark"
        in query
    )
