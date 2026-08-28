from models import (
    AdaptiveResearchState,
    Claim,
    Evidence,
    SummaryState,
    TodoItem,
)
from services.agent_eval_observation import (
    build_eval_observation,
)


def test_builder_observes_real_task_counts():
    state = SummaryState()

    state.todo_items = [
        TodoItem(
            id=1,
            title="A",
            intent="A",
            query="A",
            status="completed",
        ),
        TodoItem(
            id=2,
            title="B",
            intent="B",
            query="B",
            status="failed",
        ),
    ]

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.planned_task_count
        == 2
    )

    assert (
        observation.completed_task_count
        == 1
    )

    assert (
        observation.failed_task_count
        == 1
    )

    assert (
        observation.completed
        is False
    )


def test_partial_and_skipped_tasks_are_terminal_for_run_completion():
    state = SummaryState()

    state.todo_items = [
        TodoItem(
            id=1,
            title="A",
            intent="A",
            query="A",
            status="partial",
        ),
        TodoItem(
            id=2,
            title="B",
            intent="B",
            query="B",
            status="skipped",
        ),
    ]

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.completed
        is True
    )

    assert (
        observation.completed_task_count
        == 0
    )


def test_no_tasks_keeps_completion_unknown():
    observation = (
        build_eval_observation(
            SummaryState()
        )
    )

    assert (
        observation.completed
        is None
    )


def test_final_answer_presence_uses_structured_report():
    state = SummaryState(
        structured_report=(
            "# Final report"
        )
    )

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.final_answer_present
        is True
    )


def test_missing_report_is_observed_as_absent():
    state = SummaryState()

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.final_answer_present
        is False
    )


def test_builder_reads_sanitized_tool_traces():
    state = SummaryState()

    state.tool_execution_traces = [
        {
            "invocation_id": "tool_1",
            "tool_name": "web_search",
            "tool_source": "search",
            "status": "SUCCESS",
        },
        {
            "invocation_id": "tool_2",
            "tool_name": "docs",
            "tool_source": "mcp",
            "status": "EXECUTION_ERROR",
        },
    ]

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.tool_call_count
        == 2
    )

    assert (
        observation.successful_tool_call_count
        == 1
    )

    assert (
        observation.failed_tool_call_count
        == 1
    )

    assert (
        observation.called_tool_names
        == [
            "web_search",
            "docs",
        ]
    )


def test_empty_tool_trace_list_is_observed_not_missing():
    state = SummaryState()

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.tool_call_count
        == 0
    )

    assert (
        observation.successful_tool_call_count
        == 0
    )

    assert (
        observation.failed_tool_call_count
        == 0
    )


def test_claims_with_evidence_links_are_grounded():
    state = SummaryState()

    state.claims = [
        Claim(
            task_id=1,
            trace_id="trace_1",
            text="Grounded",
            evidence_ids=[
                "evidence_1",
            ],
        ),
        Claim(
            task_id=1,
            trace_id="trace_1",
            text="Unsupported",
            evidence_ids=[],
        ),
    ]

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.claim_count
        == 2
    )

    assert (
        observation.grounded_claim_count
        == 1
    )

    assert (
        observation.unsupported_claim_count
        == 1
    )


def test_evidence_count_is_observed_from_state():
    state = SummaryState()

    state.evidence_items = [
        Evidence(
            task_id=1,
            trace_id="trace_1",
            query="query",
            backend="test",
            source_rank=1,
        ),
        Evidence(
            task_id=1,
            trace_id="trace_1",
            query="query",
            backend="test",
            source_rank=2,
        ),
    ]

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.evidence_count
        == 2
    )


def test_adaptive_iteration_count_is_observed():
    state = SummaryState()

    state.adaptive_research_state = (
        AdaptiveResearchState(
            decision_id="decision_1",
            iteration_count=3,
        )
    )

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.adaptive_iteration_count
        == 3
    )


def test_missing_adaptive_state_remains_unknown():
    state = SummaryState()

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.adaptive_iteration_count
        is None
    )


def test_recovery_is_not_inferred_from_tool_failures():
    state = SummaryState()

    state.tool_execution_traces = [
        {
            "tool_name": "web_search",
            "status": "EXECUTION_ERROR",
            "error_type": "TimeoutError",
        }
    ]

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.recoverable_failure_count
        is None
    )

    assert (
        observation.recovered_failure_count
        is None
    )


def test_latency_is_not_faked_from_task_trace_sums():
    state = SummaryState()

    observation = (
        build_eval_observation(
            state
        )
    )

    assert (
        observation.latency_ms
        is None
    )


def test_token_and_cost_metrics_remain_unknown_without_accounting():
    observation = (
        build_eval_observation(
            SummaryState()
        )
    )

    assert (
        observation.token_usage
        is None
    )

    assert (
        observation.estimated_cost
        is None
    )


def test_observation_builder_does_not_mutate_state():
    state = SummaryState(
        structured_report="report"
    )

    before_tool_traces = list(
        state.tool_execution_traces
    )

    before_tasks = list(
        state.todo_items
    )

    build_eval_observation(
        state
    )

    assert (
        state.tool_execution_traces
        == before_tool_traces
    )

    assert (
        state.todo_items
        == before_tasks
    )


def test_observation_contains_no_decision_truth_fields():
    observation = (
        build_eval_observation(
            SummaryState()
        )
    )

    forbidden = {
        "candidate_score",
        "recommendation",
        "decision_readiness",
        "winner",
        "decision_truth",
    }

    assert not (
        forbidden
        & set(vars(observation))
    )
