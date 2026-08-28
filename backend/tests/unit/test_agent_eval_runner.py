from models import (
    Claim,
    SummaryState,
    TodoItem,
)
from services.agent_eval import (
    EvalCase,
)
from services.agent_eval_runner import (
    evaluate_research_state,
    serialize_research_eval,
)


def make_state():
    state = SummaryState(
        structured_report=(
            "# Final"
        )
    )

    state.todo_items = [
        TodoItem(
            id=1,
            title="Research",
            intent="Research",
            query="query",
            status="completed",
        )
    ]

    state.tool_execution_traces = [
        {
            "tool_name":
                "web_search",
            "status":
                "SUCCESS",
        }
    ]

    state.evidence_items = [
        object()
    ]

    state.claims = [
        Claim(
            task_id=1,
            trace_id="trace_1",
            text="Claim",
            evidence_ids=[
                "evidence_1"
            ],
        )
    ]

    return state


def test_evaluate_persisted_state():
    result = evaluate_research_state(
        research_id="research_1",
        state=make_state(),
        cases=[
            EvalCase(
                case_id="case_1",
                name="Case",
                task="Research",
                expected_tool_names=[
                    "web_search"
                ],
                require_evidence=True,
                require_final_answer=True,
            )
        ],
    )

    assert (
        result.research_id
        == "research_1"
    )

    assert (
        result.suite.case_count
        == 1
    )


def test_serialized_eval_is_json_safe():
    result = evaluate_research_state(
        research_id="research_1",
        state=make_state(),
        cases=[
            EvalCase(
                case_id="case_1",
                name="Case",
                task="Research",
                expected_tool_names=[
                    "web_search"
                ],
                require_evidence=True,
            )
        ],
    )

    payload = (
        serialize_research_eval(
            result
        )
    )

    assert (
        payload["research_id"]
        == "research_1"
    )

    assert (
        payload["evaluation"]
        ["case_count"]
        == 1
    )
