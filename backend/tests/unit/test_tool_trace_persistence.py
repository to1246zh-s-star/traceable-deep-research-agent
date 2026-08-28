from models import SummaryState
from services.research_store import (
    InMemoryResearchStore,
)


def test_tool_execution_traces_survive_store_roundtrip():
    store = InMemoryResearchStore()

    state = SummaryState(
        research_topic="tool trace"
    )

    state.tool_execution_traces = [
        {
            "invocation_id": "tool_123",
            "tool_name": "web_search",
            "tool_source": "tavily",
            "status": "SUCCESS",
            "duration_ms": 12.5,
            "error_type": None,
            "error_message": None,
            "metadata": {
                "read_only": True,
            },
        }
    ]

    research_id = store.save(state)

    restored = store.get(
        research_id
    )

    assert restored is not None

    assert (
        restored.tool_execution_traces
        == state.tool_execution_traces
    )
