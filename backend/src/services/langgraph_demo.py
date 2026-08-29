"""Deterministic offline entry point for the LangGraph compatibility layer."""

from __future__ import annotations

import json

from models import SummaryState
from services.langgraph_adapter import (
    LangGraphResearchAdapter,
    LangGraphResearchState,
    get_research_graph_mapping,
    is_langgraph_available,
)
from services.tool_runtime import ToolRegistry


def run_demo() -> LangGraphResearchState:
    """Complete the lifecycle without an LLM, search provider, or network."""
    summary_state = SummaryState(research_topic="LangGraph compatibility demo")

    def report(state: LangGraphResearchState) -> LangGraphResearchState:
        state.summary_state.structured_report = (
            "# LangGraph compatibility demo\n\n"
            "Completed through the custom-runtime adapter."
        )
        state.summary_state.running_summary = state.summary_state.structured_report
        return state

    adapter = LangGraphResearchAdapter(
        tool_registry=ToolRegistry(),
        report=report,
    )
    return adapter.run_local_demo(
        LangGraphResearchState(summary_state=summary_state)
    )


def main() -> None:
    """Print deterministic graph metadata and offline completion state."""
    result = run_demo()
    mapping = get_research_graph_mapping()
    print(  # noqa: T201 - intentional CLI output
        json.dumps(
            {
                "langgraph_available": is_langgraph_available(),
                "nodes": list(mapping.nodes),
                "conditional_routes": [
                    {
                        "source": route.source,
                        "routes": dict(route.routes),
                    }
                    for route in mapping.conditional_routes
                ],
                "terminal_reason": result.terminal_reason,
                "final_stage": result.current_stage,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
