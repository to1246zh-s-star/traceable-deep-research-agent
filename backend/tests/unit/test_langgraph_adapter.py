import inspect

import pytest

from models import ResearchStoppingDecision, SummaryState
from services.langgraph_adapter import (
    ADAPTIVE_CHECK,
    CHECKPOINT,
    CONTINUE_RESEARCH,
    FINISH_RESEARCH,
    LangGraphResearchAdapter,
    LangGraphResearchState,
    SummaryStateCheckpointBridge,
    build_research_demo_graph,
    get_research_graph_mapping,
    is_langgraph_available,
)
from services.langgraph_demo import run_demo
from services.research_store import InMemoryResearchStore
from services.tool_runtime import (
    TOOL_SUCCESS,
    ToolDefinition,
    ToolInvocation,
    ToolParameter,
    ToolRegistry,
)


def _stopping(should_continue: bool, reason: str) -> ResearchStoppingDecision:
    return ResearchStoppingDecision(
        should_continue=should_continue,
        reason=reason,
        readiness_score=0.0,
        readiness_status="UNKNOWN",
    )


def test_adapter_imports_without_langgraph_installed():
    assert isinstance(is_langgraph_available(), bool)

    if not is_langgraph_available():
        adapter = LangGraphResearchAdapter(tool_registry=ToolRegistry())
        with pytest.raises(RuntimeError, match="LangGraph is not installed"):
            build_research_demo_graph(adapter)


def test_graph_mapping_matches_real_lifecycle():
    mapping = get_research_graph_mapping()

    assert mapping.nodes == (
        "prepare",
        "plan",
        "research",
        "decision_enrichment",
        "adaptive_check",
        "report",
        "checkpoint",
    )
    route = mapping.conditional_routes[0]
    assert route.source == ADAPTIVE_CHECK
    assert dict(route.routes) == {
        CONTINUE_RESEARCH: "research",
        FINISH_RESEARCH: "report",
    }
    assert (CHECKPOINT, "END") in mapping.edges


def test_conditional_routing_uses_existing_stopping_decision():
    adapter = LangGraphResearchAdapter(tool_registry=ToolRegistry())
    summary_state = SummaryState(research_topic="routing")
    graph_state = LangGraphResearchState(summary_state=summary_state)

    summary_state.stopping_decision = _stopping(True, "actionable_gaps")
    assert adapter.route_after_adaptive_check(graph_state) == CONTINUE_RESEARCH
    assert graph_state.should_continue is True

    summary_state.stopping_decision = _stopping(False, "budget_exhausted")
    assert adapter.route_after_adaptive_check(graph_state) == FINISH_RESEARCH
    assert graph_state.should_continue is False
    assert graph_state.terminal_reason == "budget_exhausted"


def test_graph_state_references_original_summary_state():
    summary_state = SummaryState(research_topic="identity")
    graph_state = LangGraphResearchState(summary_state=summary_state)

    assert graph_state.summary_state is summary_state
    assert not hasattr(graph_state, "decision_case")
    assert not hasattr(graph_state, "evidence_items")
    assert not hasattr(graph_state, "stopping_decision")


def test_adapter_reuses_supplied_unified_tool_runtime():
    registry = ToolRegistry()
    registry.register(
        definition=ToolDefinition(
            name="offline_tool",
            description="offline",
            parameters=[ToolParameter(name="value", type="string")],
        ),
        handler=lambda arguments: {"observed": arguments["value"]},
    )
    adapter = LangGraphResearchAdapter(tool_registry=registry)

    result = adapter.invoke_tool(
        ToolInvocation(tool_name="offline_tool", arguments={"value": "ok"})
    )

    assert adapter.tool_registry is registry
    assert result.status == TOOL_SUCCESS
    assert result.output == {"observed": "ok"}


def test_adapter_introduces_no_search_provider_path():
    import services.langgraph_adapter as module

    source = inspect.getsource(module)
    assert "dispatch_search" not in source
    assert "tavily" not in source.lower()
    assert "ToolRegistry" in source
    assert "ToolInvocation" in source


def test_checkpoint_bridge_persists_original_summary_state():
    store = InMemoryResearchStore()
    summary_state = SummaryState(research_topic="checkpoint")
    bridge = SummaryStateCheckpointBridge(store=store)
    graph_state = LangGraphResearchState(summary_state=summary_state)

    research_id = bridge.save(graph_state)
    restored = bridge.load(research_id)

    assert store.get(research_id) is summary_state
    assert restored is not None
    assert restored.summary_state is summary_state
    assert restored.current_stage == CHECKPOINT


def test_offline_demo_completes_without_external_services():
    result = run_demo()

    assert result.current_stage == CHECKPOINT
    assert result.terminal_reason == "no_adaptive_continuation"
    assert result.summary_state.structured_report
    assert not result.summary_state.evidence_items
    assert not result.summary_state.tool_execution_traces


def test_local_demo_delegates_without_changing_business_semantics():
    calls = []
    summary_state = SummaryState(research_topic="semantics")

    def record(name):
        def callback(state):
            calls.append(name)
            return state

        return callback

    adapter = LangGraphResearchAdapter(
        tool_registry=ToolRegistry(),
        prepare=record("prepare"),
        plan=record("plan"),
        research=record("research"),
        decision_enrichment=record("decision_enrichment"),
        report=record("report"),
    )

    result = adapter.run_local_demo(
        LangGraphResearchState(summary_state=summary_state)
    )

    assert calls == [
        "prepare",
        "plan",
        "research",
        "decision_enrichment",
        "report",
    ]
    assert result.summary_state is summary_state
    assert summary_state.decision_case is None
    assert not summary_state.evidence_items
