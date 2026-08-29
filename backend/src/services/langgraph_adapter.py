"""Optional LangGraph orchestration compatibility for the research Agent.

The custom runtime remains authoritative for state, tools, stopping,
decision semantics, reporting, replay, and persistence. This module only
maps those existing boundaries to graph orchestration concepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from models import SummaryState
from services.tool_runtime import ToolInvocation, ToolRegistry, ToolResult

try:  # Optional integration: production does not require LangGraph.
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - depends on optional environment
    END = "__end__"
    START = "__start__"
    StateGraph = None


PREPARE = "prepare"
PLAN = "plan"
RESEARCH = "research"
DECISION_ENRICHMENT = "decision_enrichment"
ADAPTIVE_CHECK = "adaptive_check"
REPORT = "report"
CHECKPOINT = "checkpoint"

CONTINUE_RESEARCH = "continue_research"
FINISH_RESEARCH = "finish_research"


@dataclass(kw_only=True)
class LangGraphResearchState:
    """Thin execution wrapper referencing the authoritative SummaryState."""

    summary_state: SummaryState
    current_stage: str = PREPARE
    current_task_id: int | None = None
    should_continue: bool = False
    terminal_reason: str | None = None


@dataclass(kw_only=True, frozen=True)
class ConditionalRoute:
    """Inspectable conditional edge in the compatibility mapping."""

    source: str
    routes: tuple[tuple[str, str], ...]


@dataclass(kw_only=True, frozen=True)
class ResearchGraphMapping:
    """Framework-independent representation of the demo graph."""

    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    conditional_routes: tuple[ConditionalRoute, ...]


RESEARCH_GRAPH_MAPPING = ResearchGraphMapping(
    nodes=(
        PREPARE,
        PLAN,
        RESEARCH,
        DECISION_ENRICHMENT,
        ADAPTIVE_CHECK,
        REPORT,
        CHECKPOINT,
    ),
    edges=(
        ("START", PREPARE),
        (PREPARE, PLAN),
        (PLAN, RESEARCH),
        (RESEARCH, DECISION_ENRICHMENT),
        (DECISION_ENRICHMENT, ADAPTIVE_CHECK),
        (REPORT, CHECKPOINT),
        (CHECKPOINT, "END"),
    ),
    conditional_routes=(
        ConditionalRoute(
            source=ADAPTIVE_CHECK,
            routes=(
                (CONTINUE_RESEARCH, RESEARCH),
                (FINISH_RESEARCH, REPORT),
            ),
        ),
    ),
)


class ResearchStoreBoundary(Protocol):
    """Existing store surface used by the checkpoint compatibility bridge."""

    def save(self, state: SummaryState, **kwargs: Any) -> str:
        """Persist an authoritative research state."""
        ...

    def get(self, research_id: str) -> SummaryState | None:
        """Load an authoritative research state."""
        ...


@dataclass(kw_only=True)
class SummaryStateCheckpointBridge:
    """Persist and restore the original SummaryState through its real store."""

    store: ResearchStoreBoundary

    def save(self, state: LangGraphResearchState) -> str:
        """Persist the wrapped original state without converting it."""
        return self.store.save(state.summary_state)

    def load(self, research_id: str) -> LangGraphResearchState | None:
        """Restore the original state inside a new execution wrapper."""
        summary_state = self.store.get(research_id)
        if summary_state is None:
            return None
        return LangGraphResearchState(
            summary_state=summary_state,
            current_stage=CHECKPOINT,
        )


StateNode = Callable[[LangGraphResearchState], LangGraphResearchState | None]


def _identity_node(state: LangGraphResearchState) -> LangGraphResearchState:
    return state


@dataclass(kw_only=True)
class LangGraphResearchAdapter:
    """Map existing Agent services onto optional graph nodes.

    Callbacks should delegate to the existing ``DeepResearchAgent`` services.
    The adapter does not implement planning, search, scoring, or reporting.
    """

    tool_registry: ToolRegistry
    prepare: StateNode = _identity_node
    plan: StateNode = _identity_node
    research: StateNode = _identity_node
    decision_enrichment: StateNode = _identity_node
    report: StateNode = _identity_node
    checkpoint_bridge: SummaryStateCheckpointBridge | None = None
    mapping: ResearchGraphMapping = field(default=RESEARCH_GRAPH_MAPPING)

    def invoke_tool(self, invocation: ToolInvocation) -> ToolResult:
        """Delegate external execution to the unified production runtime."""
        return self.tool_registry.invoke(invocation)

    def route_after_adaptive_check(self, state: LangGraphResearchState) -> str:
        """Route from the existing deterministic stopping decision."""
        stopping = state.summary_state.stopping_decision
        should_continue = bool(stopping is not None and stopping.should_continue)
        state.should_continue = should_continue

        if should_continue:
            state.terminal_reason = None
            return CONTINUE_RESEARCH

        state.terminal_reason = (
            stopping.reason
            if stopping is not None and stopping.reason
            else "no_adaptive_continuation"
        )
        return FINISH_RESEARCH

    def node(self, name: str, callback: StateNode) -> StateNode:
        """Wrap a delegated service callback with execution-stage metadata."""

        def execute(state: LangGraphResearchState) -> LangGraphResearchState:
            state.current_stage = name
            result = callback(state)
            return result if result is not None else state

        return execute

    def adaptive_check_node(
        self,
        state: LangGraphResearchState,
    ) -> LangGraphResearchState:
        """Mark entry into the deterministic adaptive routing boundary."""
        state.current_stage = ADAPTIVE_CHECK
        return state

    def checkpoint_node(
        self,
        state: LangGraphResearchState,
    ) -> LangGraphResearchState:
        """Delegate persistence to the existing research store boundary."""
        state.current_stage = CHECKPOINT
        if self.checkpoint_bridge is not None:
            self.checkpoint_bridge.save(state)
        return state

    def run_local_demo(
        self,
        state: LangGraphResearchState,
        *,
        max_adaptive_iterations: int = 10,
    ) -> LangGraphResearchState:
        """Run the same mapping locally without LangGraph or live services."""
        if max_adaptive_iterations < 0:
            raise ValueError("max_adaptive_iterations must be >= 0")

        state = self.node(PREPARE, self.prepare)(state)
        state = self.node(PLAN, self.plan)(state)
        iterations = 0

        while True:
            state = self.node(RESEARCH, self.research)(state)
            state = self.node(
                DECISION_ENRICHMENT,
                self.decision_enrichment,
            )(state)
            state = self.adaptive_check_node(state)
            route = self.route_after_adaptive_check(state)
            if route == FINISH_RESEARCH:
                break
            iterations += 1
            if iterations >= max_adaptive_iterations:
                state.should_continue = False
                state.terminal_reason = "demo_iteration_limit"
                break

        state = self.node(REPORT, self.report)(state)
        return self.checkpoint_node(state)


def is_langgraph_available() -> bool:
    """Return whether the optional LangGraph package can be used."""
    return StateGraph is not None


def get_research_graph_mapping() -> ResearchGraphMapping:
    """Return the deterministic, inspectable lifecycle mapping."""
    return RESEARCH_GRAPH_MAPPING


def build_research_demo_graph(adapter: LangGraphResearchAdapter) -> Any:
    """Build a LangGraph graph that delegates every node to the adapter."""
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph is not installed; install the 'langgraph' optional dependency"
        )

    graph = StateGraph(LangGraphResearchState)
    graph.add_node(PREPARE, adapter.node(PREPARE, adapter.prepare))
    graph.add_node(PLAN, adapter.node(PLAN, adapter.plan))
    graph.add_node(RESEARCH, adapter.node(RESEARCH, adapter.research))
    graph.add_node(
        DECISION_ENRICHMENT,
        adapter.node(DECISION_ENRICHMENT, adapter.decision_enrichment),
    )
    graph.add_node(ADAPTIVE_CHECK, adapter.adaptive_check_node)
    graph.add_node(REPORT, adapter.node(REPORT, adapter.report))
    graph.add_node(CHECKPOINT, adapter.checkpoint_node)

    graph.add_edge(START, PREPARE)
    graph.add_edge(PREPARE, PLAN)
    graph.add_edge(PLAN, RESEARCH)
    graph.add_edge(RESEARCH, DECISION_ENRICHMENT)
    graph.add_edge(DECISION_ENRICHMENT, ADAPTIVE_CHECK)
    graph.add_conditional_edges(
        ADAPTIVE_CHECK,
        adapter.route_after_adaptive_check,
        {
            CONTINUE_RESEARCH: RESEARCH,
            FINISH_RESEARCH: REPORT,
        },
    )
    graph.add_edge(REPORT, CHECKPOINT)
    graph.add_edge(CHECKPOINT, END)
    return graph.compile()
