from main import _build_research_replay
from models import SummaryState


def test_replay_exposes_sanitized_tool_execution_traces():
    state = SummaryState(
        research_topic="Replay"
    )

    state.tool_execution_traces = [
        {
            "invocation_id": "tool_abc",
            "tool_name": "web_search",
            "tool_source": "tavily",
            "status": "SUCCESS",
            "duration_ms": 18.2,
            "error_type": None,
            "error_message": None,
            "metadata": {
                "read_only": True,
            },
        }
    ]

    replay = _build_research_replay(
        "research_test",
        state,
    )

    assert (
        replay[
            "tool_execution_traces"
        ][0]["tool_name"]
        == "web_search"
    )


def test_replay_tool_trace_has_no_arguments_or_outputs():
    state = SummaryState()

    state.tool_execution_traces = [
        {
            "invocation_id": "tool_safe",
            "tool_name": "web_search",
            "tool_source": "search",
            "status": "SUCCESS",
            "duration_ms": 1.0,
            "metadata": {},
        }
    ]

    replay = _build_research_replay(
        "research_test",
        state,
    )

    trace = replay[
        "tool_execution_traces"
    ][0]

    assert "arguments" not in trace
    assert "output" not in trace
