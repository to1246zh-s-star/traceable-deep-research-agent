from models import (
    AdaptiveResearchIteration,
    ResearchAnalysis,
    ResearchGap,
    ResearchStoppingDecision,
    SummaryState,
)
from services.retrieval_yield import (
    RetrievalSnapshot,
    apply_diminishing_returns_stop,
    assess_iteration_retrieval_yield,
    capture_retrieval_snapshot,
    consecutive_low_yield_count,
)


def iteration(
    *,
    number=1,
    status="completed",
):
    return AdaptiveResearchIteration(
        decision_id="dec_test",
        iteration_number=number,
        status=status,
    )


def stopping(
    *,
    should_continue=True,
    reason="continue_research",
):
    return ResearchStoppingDecision(
        should_continue=should_continue,
        reason=reason,
        readiness_score=0.5,
        readiness_status="NOT_READY",
    )


def snapshot(
    *,
    evidence=None,
    authorities=None,
    matches=None,
    gaps=1,
):
    return RetrievalSnapshot(
        evidence_ids=set(
            evidence or []
        ),
        authority_types=set(
            authorities or []
        ),
        strategy_matches=set(
            matches or []
        ),
        open_gap_count=gaps,
    )


def test_no_new_information_is_no_yield():
    item = iteration()

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(
            evidence=["e1"],
        ),
        snapshot(
            evidence=["e1"],
        ),
    )

    assert status == "NO_YIELD"
    assert item.new_evidence_count == 0


def test_only_new_documents_is_low_yield():
    item = iteration()

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(
            evidence=["e1"],
        ),
        snapshot(
            evidence=[
                "e1",
                "e2",
                "e3",
            ],
        ),
    )

    assert status == "LOW_YIELD"
    assert item.new_evidence_count == 2


def test_new_authority_is_moderate_yield():
    item = iteration()

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(
            evidence=["e1"],
            authorities=[
                "OFFICIAL_DOCUMENTATION"
            ],
        ),
        snapshot(
            evidence=[
                "e1",
                "e2",
            ],
            authorities=[
                "OFFICIAL_DOCUMENTATION",
                "ACADEMIC",
            ],
        ),
    )

    assert status == "MODERATE_YIELD"

    assert item.new_authority_types == [
        "ACADEMIC"
    ]


def test_one_new_strategy_match_is_moderate():
    item = iteration()

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(),
        snapshot(
            evidence=["e1"],
            matches=[
                "cand|crit|benchmark"
            ],
        ),
    )

    assert status == "MODERATE_YIELD"


def test_multiple_strategy_matches_is_high():
    item = iteration()

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(),
        snapshot(
            evidence=[
                "e1",
                "e2",
            ],
            matches=[
                "cand|crit|benchmark",
                "cand|crit|academic_paper",
            ],
        ),
    )

    assert status == "HIGH_YIELD"


def test_strategy_match_plus_gap_reduction_is_high():
    item = iteration()

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(
            gaps=3,
        ),
        snapshot(
            evidence=["e1"],
            matches=[
                "cand|crit|benchmark"
            ],
            gaps=2,
        ),
    )

    assert status == "HIGH_YIELD"


def test_failed_iteration_is_unknown_not_no_yield():
    item = iteration(
        status="failed",
    )

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(),
        snapshot(),
    )

    assert status == "UNKNOWN"


def test_unknown_breaks_low_yield_chain():
    first = iteration(
        number=1
    )
    first.retrieval_yield_status = (
        "LOW_YIELD"
    )

    second = iteration(
        number=2,
        status="failed",
    )
    second.retrieval_yield_status = (
        "UNKNOWN"
    )

    third = iteration(
        number=3
    )
    third.retrieval_yield_status = (
        "NO_YIELD"
    )

    assert (
        consecutive_low_yield_count(
            [
                first,
                second,
                third,
            ]
        )
        == 1
    )


def test_one_low_yield_iteration_does_not_stop():
    item = iteration()
    item.retrieval_yield_status = (
        "LOW_YIELD"
    )

    decision = (
        apply_diminishing_returns_stop(
            stopping(),
            [item],
        )
    )

    assert decision is not None
    assert decision.should_continue is True
    assert (
        decision
        .consecutive_low_yield_iterations
        == 1
    )


def test_two_consecutive_low_yield_iterations_stop():
    first = iteration(
        number=1
    )
    first.retrieval_yield_status = (
        "LOW_YIELD"
    )

    second = iteration(
        number=2
    )
    second.retrieval_yield_status = (
        "NO_YIELD"
    )

    decision = (
        apply_diminishing_returns_stop(
            stopping(),
            [
                first,
                second,
            ],
        )
    )

    assert decision is not None
    assert decision.should_continue is False
    assert (
        decision.reason
        == "diminishing_returns"
    )

    assert (
        decision
        .consecutive_low_yield_iterations
        == 2
    )


def test_moderate_yield_resets_low_yield_chain():
    first = iteration(
        number=1
    )
    first.retrieval_yield_status = (
        "LOW_YIELD"
    )

    second = iteration(
        number=2
    )
    second.retrieval_yield_status = (
        "MODERATE_YIELD"
    )

    third = iteration(
        number=3
    )
    third.retrieval_yield_status = (
        "NO_YIELD"
    )

    assert (
        consecutive_low_yield_count(
            [
                first,
                second,
                third,
            ]
        )
        == 1
    )


def test_existing_stronger_stop_reason_is_preserved():
    first = iteration(
        number=1
    )
    first.retrieval_yield_status = (
        "LOW_YIELD"
    )

    second = iteration(
        number=2
    )
    second.retrieval_yield_status = (
        "NO_YIELD"
    )

    original = stopping(
        should_continue=False,
        reason="decision_ready",
    )

    result = apply_diminishing_returns_stop(
        original,
        [
            first,
            second,
        ],
    )

    assert result.reason == "decision_ready"


def test_capture_snapshot_tracks_strategy_matches():
    state = SummaryState(
        research_topic="test",
        research_analysis=ResearchAnalysis(
            decision_id="dec_test",
            research_gaps=[
                ResearchGap(
                    gap_id="gap_1",
                    candidate_id="cand_a",
                    criterion_id="crit_scale",
                    gap_type="low_coverage",
                    severity=0.8,
                    description="Need evidence",
                    matched_source_types=[
                        "benchmark",
                    ],
                )
            ],
        ),
    )

    result = capture_retrieval_snapshot(
        state
    )

    assert (
        "cand_a|crit_scale|benchmark"
        in result.strategy_matches
    )


def test_yield_assessment_is_deterministic():
    before = snapshot(
        evidence=["e1"],
    )

    after = snapshot(
        evidence=[
            "e1",
            "e2",
        ],
        authorities=[
            "ACADEMIC",
        ],
    )

    first = iteration()
    second = iteration()

    assert (
        assess_iteration_retrieval_yield(
            first,
            before,
            after,
        )
        == assess_iteration_retrieval_yield(
            second,
            before,
            after,
        )
    )

    assert (
        first.new_authority_types
        == second.new_authority_types
    )


def test_legacy_iteration_without_status_is_unknown():
    class LegacyIteration:
        task_ids = [1]

    item = LegacyIteration()

    status = assess_iteration_retrieval_yield(
        item,
        snapshot(),
        snapshot(),
    )

    assert status == "UNKNOWN"

    assert (
        item.retrieval_yield_status
        == "UNKNOWN"
    )

    assert (
        item.retrieval_yield_reasons
        == ["iteration_status_unavailable"]
    )
