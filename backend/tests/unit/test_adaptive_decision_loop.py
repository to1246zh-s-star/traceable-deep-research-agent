from models import (
    DecisionCase,
    ResearchAnalysis,
    ResearchGap,
    ResearchStoppingDecision,
    SummaryState,
)
from services.adaptive_decision_loop import (
    ensure_adaptive_runtime,
    record_adaptive_iteration_usage,
    run_adaptive_decision_loop,
)


def make_decision():
    return DecisionCase(
        decision_id="dec_loop",
        question="Choose A or B",
    )


def continue_decision():
    return ResearchStoppingDecision(
        should_continue=True,
        reason="research_needed",
        readiness_score=0.4,
        readiness_status="NOT_READY",
        readiness_improvement=None,
        actionable_gap_count=1,
        blocking_budget_limits=[],
    )


def stop_decision():
    return ResearchStoppingDecision(
        should_continue=False,
        reason="decision_ready",
        readiness_score=0.8,
        readiness_status="READY",
        readiness_improvement=0.4,
        actionable_gap_count=0,
        blocking_budget_limits=[],
    )


def make_analysis():
    return ResearchAnalysis(
        decision_id="dec_loop",
        research_gaps=[
            ResearchGap(
                gap_id="gap_1",
                candidate_id="cand_a",
                criterion_id="crit_1",
                gap_type="low_coverage",
                severity=0.8,
                description="Need evidence",
                suggested_query="candidate A benchmark",
            )
        ],
    )


def test_runtime_objects_are_created_once_and_reused():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
    )

    budget1, usage1, adaptive1 = (
        ensure_adaptive_runtime(state)
    )

    budget2, usage2, adaptive2 = (
        ensure_adaptive_runtime(state)
    )

    assert budget1 is budget2
    assert usage1 is usage2
    assert adaptive1 is adaptive2

    assert state.research_budget is budget1
    assert state.research_usage is usage1
    assert state.adaptive_research_state is adaptive1


def test_record_adaptive_iteration_usage_accumulates():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
    )

    _, usage, _ = ensure_adaptive_runtime(
        state
    )

    record_adaptive_iteration_usage(
        usage,
        task_count=2,
    )

    record_adaptive_iteration_usage(
        usage,
        task_count=3,
    )

    assert usage.iterations == 2
    assert usage.tasks == 5


def test_loop_executes_followup_then_recalculates_decision():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        research_analysis=make_analysis(),
        stopping_decision=continue_decision(),
    )

    calls = []

    class Iteration:
        task_ids = [10, 11]

    def execute_followups(
        state,
        analysis,
        adaptive_state,
        *,
        max_tasks,
    ):
        calls.append("followup")
        return Iteration()

    def execute_intelligence(
        state,
        *,
        research_budget,
        research_usage,
    ):
        calls.append("decision")

        assert research_usage.iterations == 1
        assert research_usage.tasks == 2

        state.stopping_decision = stop_decision()

        return state

    result = run_adaptive_decision_loop(
        state,
        execute_followups=execute_followups,
        execute_decision_intelligence=execute_intelligence,
    )

    assert result is state
    assert calls == [
        "followup",
        "decision",
    ]

    assert state.research_usage is not None
    assert state.research_usage.iterations == 1
    assert state.research_usage.tasks == 2


def test_loop_repeats_until_stopping_decision_changes():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        research_analysis=make_analysis(),
        stopping_decision=continue_decision(),
    )

    followup_calls = 0
    decision_calls = 0

    class Iteration:
        task_ids = [1]

    def execute_followups(
        state,
        analysis,
        adaptive_state,
        *,
        max_tasks,
    ):
        nonlocal followup_calls

        followup_calls += 1

        return Iteration()

    def execute_intelligence(
        state,
        *,
        research_budget,
        research_usage,
    ):
        nonlocal decision_calls

        decision_calls += 1

        if decision_calls >= 2:
            state.stopping_decision = (
                stop_decision()
            )

        return state

    run_adaptive_decision_loop(
        state,
        execute_followups=execute_followups,
        execute_decision_intelligence=execute_intelligence,
    )

    assert followup_calls == 2
    assert decision_calls == 2

    assert state.research_usage.iterations == 2
    assert state.research_usage.tasks == 2


def test_loop_stops_when_followup_planner_returns_none():
    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        research_analysis=make_analysis(),
        stopping_decision=continue_decision(),
    )

    decision_calls = []

    def execute_followups(
        state,
        analysis,
        adaptive_state,
        *,
        max_tasks,
    ):
        return None

    def execute_intelligence(
        state,
        *,
        research_budget,
        research_usage,
    ):
        decision_calls.append(True)
        return state

    run_adaptive_decision_loop(
        state,
        execute_followups=execute_followups,
        execute_decision_intelligence=execute_intelligence,
    )

    assert decision_calls == []

    assert state.research_usage.iterations == 0
    assert state.research_usage.tasks == 0


def test_non_decision_state_is_noop():
    state = SummaryState(
        research_topic="Explain transformers",
    )

    result = run_adaptive_decision_loop(
        state,
        execute_followups=lambda *args, **kwargs: None,
        execute_decision_intelligence=lambda *args, **kwargs: None,
    )

    assert result is state
    assert state.research_usage is None
    assert state.adaptive_research_state is None


def test_adaptive_loop_records_retrieval_yield():
    from models import (
        AdaptiveResearchIteration,
        Evidence,
    )

    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        research_analysis=make_analysis(),
        stopping_decision=continue_decision(),
    )

    calls = {
        "followups": 0,
        "intelligence": 0,
    }

    def execute_followups(
        state_arg,
        analysis,
        adaptive_state,
        *,
        max_tasks,
    ):
        calls["followups"] += 1

        if calls["followups"] > 1:
            return None

        iteration = AdaptiveResearchIteration(
            decision_id="dec_loop",
            iteration_number=1,
            task_ids=[1],
            status="completed",
        )

        adaptive_state.iteration_count = 1
        adaptive_state.iterations.append(
            iteration
        )

        state_arg.evidence_items.append(
            Evidence(
                evidence_id="evi_new",
                task_id=1,
                trace_id="trace_new",
                query="benchmark",
                backend="web",
                source_title="Benchmark",
            )
        )

        return iteration

    def execute_intelligence(
        state_arg,
        *,
        research_budget,
        research_usage,
    ):
        calls["intelligence"] += 1

        state_arg.stopping_decision = (
            continue_decision()
        )

        return state_arg

    run_adaptive_decision_loop(
        state,
        execute_followups=(
            execute_followups
        ),
        execute_decision_intelligence=(
            execute_intelligence
        ),
    )

    iteration = (
        state
        .adaptive_research_state
        .iterations[0]
    )

    assert (
        iteration.retrieval_yield_status
        == "LOW_YIELD"
    )

    assert (
        iteration.new_evidence_count
        == 1
    )


def test_adaptive_loop_stops_after_repeated_no_yield():
    from models import (
        AdaptiveResearchIteration,
    )

    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        research_analysis=make_analysis(),
        stopping_decision=continue_decision(),
    )

    call_count = 0

    def execute_followups(
        state_arg,
        analysis,
        adaptive_state,
        *,
        max_tasks,
    ):
        nonlocal call_count
        call_count += 1

        iteration = AdaptiveResearchIteration(
            decision_id="dec_loop",
            iteration_number=call_count,
            task_ids=[call_count],
            status="completed",
        )

        adaptive_state.iteration_count = (
            call_count
        )

        adaptive_state.iterations.append(
            iteration
        )

        return iteration

    def execute_intelligence(
        state_arg,
        *,
        research_budget,
        research_usage,
    ):
        state_arg.stopping_decision = (
            continue_decision()
        )

        return state_arg

    run_adaptive_decision_loop(
        state,
        execute_followups=(
            execute_followups
        ),
        execute_decision_intelligence=(
            execute_intelligence
        ),
    )

    assert call_count == 2

    assert (
        state.stopping_decision.reason
        == "diminishing_returns"
    )

    assert (
        state
        .stopping_decision
        .consecutive_low_yield_iterations
        == 2
    )


def test_adaptive_loop_attaches_evidence_saturation():
    from models import (
        AdaptiveResearchIteration,
        Evidence,
    )

    state = SummaryState(
        research_topic="A vs B",
        decision_case=make_decision(),
        research_analysis=make_analysis(),
        stopping_decision=continue_decision(),
    )

    calls = 0

    repeated_content = (
        "Independent benchmark latency throughput "
        "memory concurrency vector search workload"
    )

    state.evidence_items.append(
        Evidence(
            evidence_id="old",
            task_id=0,
            trace_id="old_trace",
            query="old",
            backend="web",
            source_title="Old benchmark",
            source_url=(
                "https://old.example/benchmark"
            ),
            snippet=repeated_content,
        )
    )

    def execute_followups(
        state_arg,
        analysis,
        adaptive_state,
        *,
        max_tasks,
    ):
        nonlocal calls
        calls += 1

        if calls > 1:
            return None

        iteration = AdaptiveResearchIteration(
            decision_id="dec_loop",
            iteration_number=1,
            task_ids=[1],
            status="completed",
        )

        adaptive_state.iteration_count = 1
        adaptive_state.iterations.append(
            iteration
        )

        state_arg.evidence_items.extend([
            Evidence(
                evidence_id="new_1",
                task_id=1,
                trace_id="trace_1",
                query="benchmark",
                backend="web",
                source_title="Mirror benchmark A",
                source_url=(
                    "https://mirror-a.example/result"
                ),
                snippet=repeated_content,
            ),
            Evidence(
                evidence_id="new_2",
                task_id=1,
                trace_id="trace_2",
                query="benchmark",
                backend="web",
                source_title="Mirror benchmark B",
                source_url=(
                    "https://mirror-b.example/result"
                ),
                snippet=repeated_content,
            ),
        ])

        return iteration

    def execute_intelligence(
        state_arg,
        *,
        research_budget,
        research_usage,
    ):
        state_arg.stopping_decision = (
            stop_decision()
        )

        return state_arg

    run_adaptive_decision_loop(
        state,
        execute_followups=(
            execute_followups
        ),
        execute_decision_intelligence=(
            execute_intelligence
        ),
    )

    item = (
        state
        .adaptive_research_state
        .iterations[0]
    )

    assert (
        item.evidence_saturation_status
        == "HIGH_SATURATION"
    )

    assert (
        item.near_duplicate_content_ratio
        == 1.0
    )
