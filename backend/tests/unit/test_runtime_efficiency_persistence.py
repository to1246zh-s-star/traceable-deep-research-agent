from models import SummaryState
from services.research_store import SQLiteResearchStore


def test_runtime_efficiency_round_trip(tmp_path):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    state = SummaryState(
        research_topic="Efficiency"
    )

    state.runtime_efficiency.latency_ms = 1234.5
    state.runtime_efficiency.llm_call_count = 3

    research_id = store.save(
        state
    )

    loaded = store.get(
        research_id
    )

    assert loaded is not None
    assert loaded.runtime_efficiency.latency_ms == 1234.5
    assert loaded.runtime_efficiency.llm_call_count == 3
    assert loaded.runtime_efficiency.total_tokens is None
    assert loaded.runtime_efficiency.estimated_cost is None
