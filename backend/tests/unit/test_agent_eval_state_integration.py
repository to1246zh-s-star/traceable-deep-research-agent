from models import (
    Claim,
    SummaryState,
    TodoItem,
)
from services.agent_eval import (
    EVAL_PASS,
    EvalCase,
    evaluate_case,
)
from services.agent_eval_observation import (
    build_eval_observation,
)


def test_real_state_can_be_evaluated_end_to_end():
    state = SummaryState(
        structured_report=(
            "# Recommendation"
        )
    )

    state.todo_items = [
        TodoItem(
            id=1,
            title="Research",
            intent="Collect evidence",
            query="official docs",
            status="completed",
        )
    ]

    state.tool_execution_traces = [
        {
            "invocation_id":
                "tool_test",
            "tool_name":
                "web_search",
            "tool_source":
                "search",
            "status":
                "SUCCESS",
        }
    ]

    state.claims = [
        Claim(
            task_id=1,
            trace_id="trace_test",
            text="Supported claim",
            evidence_ids=[
                "evidence_test",
            ],
        )
    ]

    # The evaluation contract only requires an observed evidence count.
    # Existing state evidence semantics remain owned by the research layer.
    state.evidence_items = [
        object()
    ]

    case = EvalCase(
        case_id="state_case",
        name="State integration",
        task="Research a question",
        expected_tool_names=[
            "web_search",
        ],
        require_evidence=True,
        require_final_answer=True,
    )

    observation = (
        build_eval_observation(
            state
        )
    )

    # Explicitly provide a recovery observation for this test case because
    # persisted state does not yet contain deterministic recovery accounting.
    observation.recoverable_failure_count = 1
    observation.recovered_failure_count = 1

    result = evaluate_case(
        case,
        observation,
    )

    assert (
        result.overall_status
        == EVAL_PASS
    )
