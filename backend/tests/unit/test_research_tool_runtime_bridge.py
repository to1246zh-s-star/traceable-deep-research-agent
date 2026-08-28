from threading import Lock

from config import Configuration
from models import SummaryState
from services.tool_runtime import (
    TOOL_EXECUTION_ERROR,
    ToolRegistry,
)
from agent import DeepResearchAgent


def make_agent():
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    agent.config = Configuration(
        fetch_full_page=False,
    )

    agent._state_lock = Lock()

    agent._research_tool_registry = (
        ToolRegistry()
    )

    agent._register_research_runtime_tools()

    return agent


def test_research_search_bridge_preserves_dispatch_contract(
    monkeypatch,
):
    agent = make_agent()
    state = SummaryState(
        research_topic="test"
    )

    calls = []

    def fake_dispatch(
        query,
        config,
        loop_count,
    ):
        calls.append(
            (
                query,
                loop_count,
            )
        )

        return (
            {
                "results": [
                    {
                        "title": "A",
                    }
                ],
                "degraded": False,
            },
            ["notice"],
            "answer",
            "tavily",
        )

    monkeypatch.setattr(
        "agent.dispatch_search",
        fake_dispatch,
    )

    (
        payload,
        notices,
        answer,
        backend,
    ) = agent._invoke_research_search_tool(
        state,
        query="vector db",
        loop_count=3,
    )

    assert calls == [
        ("vector db", 3)
    ]

    assert payload["results"] == [
        {
            "title": "A",
        }
    ]

    assert notices == ["notice"]
    assert answer == "answer"
    assert backend == "tavily"


def test_research_search_bridge_records_tool_trace(
    monkeypatch,
):
    agent = make_agent()
    state = SummaryState()

    monkeypatch.setattr(
        "agent.dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [],
                "degraded": False,
            },
            [],
            None,
            "tavily",
        ),
    )

    agent._invoke_research_search_tool(
        state,
        query="test",
        loop_count=0,
    )

    assert (
        len(
            state.tool_execution_traces
        )
        == 1
    )

    trace = (
        state.tool_execution_traces[0]
    )

    assert (
        trace["tool_name"]
        == "web_search"
    )

    assert (
        trace["tool_source"]
        == "search"
    )

    assert (
        trace["status"]
        == "SUCCESS"
    )

    assert "arguments" not in trace


def test_degraded_search_remains_successful_tool_observation(
    monkeypatch,
):
    agent = make_agent()
    state = SummaryState()

    monkeypatch.setattr(
        "agent.dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [],
                "degraded": True,
                "error_type": (
                    "TimeoutError"
                ),
            },
            [
                "Search provider degraded"
            ],
            None,
            "tavily",
        ),
    )

    (
        payload,
        notices,
        answer,
        backend,
    ) = agent._invoke_research_search_tool(
        state,
        query="test",
        loop_count=0,
    )

    assert (
        payload["degraded"]
        is True
    )

    assert (
        payload["error_type"]
        == "TimeoutError"
    )

    assert notices
    assert answer is None
    assert backend == "tavily"

    assert (
        state
        .tool_execution_traces[0]
        ["status"]
        == "SUCCESS"
    )


def test_tool_trace_does_not_change_decision_state(
    monkeypatch,
):
    agent = make_agent()

    state = SummaryState()

    monkeypatch.setattr(
        "agent.dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [],
                "degraded": False,
            },
            [],
            None,
            "tavily",
        ),
    )

    agent._invoke_research_search_tool(
        state,
        query="candidate A wins",
        loop_count=0,
    )

    assert state.decision_case is None
    assert state.decision_evaluation is None
    assert state.decision_readiness is None


def test_research_search_runtime_preserves_empty_search(
    monkeypatch,
):
    agent = make_agent()
    state = SummaryState()

    monkeypatch.setattr(
        "agent.dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [],
                "degraded": False,
                "notices": [],
            },
            [],
            None,
            "tavily",
        ),
    )

    payload, _, _, _ = (
        agent._invoke_research_search_tool(
            state,
            query="nothing",
            loop_count=0,
        )
    )

    assert payload["results"] == []
    assert payload["degraded"] is False


def test_research_tool_registry_is_lazily_initialized(
    monkeypatch,
):
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    agent.config = Configuration(
        fetch_full_page=False,
    )
    agent._state_lock = Lock()

    assert not hasattr(
        agent,
        "_research_tool_registry",
    )

    monkeypatch.setattr(
        "agent.dispatch_search",
        lambda query, config, loop_count: (
            {
                "results": [],
                "degraded": False,
            },
            [],
            None,
            "tavily",
        ),
    )

    state = SummaryState()

    agent._invoke_research_search_tool(
        state,
        query="lazy runtime",
        loop_count=0,
    )

    assert hasattr(
        agent,
        "_research_tool_registry",
    )

    assert (
        agent._research_tool_registry.get(
            "web_search"
        )
        is not None
    )


def test_research_tool_registration_is_idempotent():
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    agent.config = Configuration(
        fetch_full_page=False,
    )
    agent._state_lock = Lock()

    registry = (
        agent._get_research_tool_registry()
    )

    first = registry.get(
        "web_search"
    )

    agent._register_research_runtime_tools()

    second = registry.get(
        "web_search"
    )

    assert first is second


def test_research_search_bridge_reraises_original_exception(
    monkeypatch,
):
    agent = make_agent()
    state = SummaryState()

    error = TimeoutError(
        "search timed out"
    )

    def fail(
        query,
        config,
        loop_count,
    ):
        raise error

    monkeypatch.setattr(
        "agent.dispatch_search",
        fail,
    )

    try:
        agent._invoke_research_search_tool(
            state,
            query="timeout",
            loop_count=0,
        )
    except TimeoutError as exc:
        assert exc is error
    else:
        raise AssertionError(
            "original TimeoutError was not re-raised"
        )

    assert (
        state.tool_execution_traces[
            0
        ]["status"]
        == TOOL_EXECUTION_ERROR
    )

    assert (
        state.tool_execution_traces[
            0
        ]["error_type"]
        == "TimeoutError"
    )
