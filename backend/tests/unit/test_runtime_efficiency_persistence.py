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
    state.runtime_efficiency.prompt_tokens = 1000
    state.runtime_efficiency.completion_tokens = 500
    state.runtime_efficiency.total_tokens = 1500
    state.runtime_efficiency.llm_usage_complete = True
    state.runtime_efficiency.estimated_cost = 0.004
    state.runtime_efficiency.cost_currency = "USD"
    state.runtime_efficiency.cost_basis = "per_1m_tokens"

    research_id = store.save(
        state
    )

    loaded = store.get(
        research_id
    )

    assert loaded is not None
    assert loaded.runtime_efficiency.latency_ms == 1234.5
    assert loaded.runtime_efficiency.llm_call_count == 3
    assert loaded.runtime_efficiency.total_tokens == 1500
    assert loaded.runtime_efficiency.estimated_cost == 0.004
    assert loaded.runtime_efficiency.cost_currency == "USD"
    assert loaded.runtime_efficiency.cost_basis == "per_1m_tokens"
