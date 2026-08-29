from main import _build_research_replay
from models import SummaryState


def test_replay_exposes_runtime_efficiency_without_changing_truth():
    state = SummaryState(research_topic="Efficiency replay")
    state.runtime_efficiency.latency_ms = 250.5
    state.runtime_efficiency.llm_call_count = 2
    state.runtime_efficiency.prompt_tokens = 1000
    state.runtime_efficiency.completion_tokens = 500
    state.runtime_efficiency.total_tokens = 1500
    state.runtime_efficiency.llm_usage_complete = True
    state.runtime_efficiency.estimated_cost = 0.004
    state.runtime_efficiency.cost_currency = "USD"
    state.runtime_efficiency.cost_basis = "per_1m_tokens"

    payload = _build_research_replay("research_efficiency", state)

    assert payload["runtime_efficiency"] == {
        "latency_ms": 250.5,
        "llm_call_count": 2,
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500,
        "llm_usage_complete": True,
        "estimated_cost": 0.004,
        "cost_currency": "USD",
        "cost_basis": "per_1m_tokens",
    }
    assert state.decision_case is None
    assert not state.evidence_items
