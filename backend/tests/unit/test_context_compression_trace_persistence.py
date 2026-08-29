from dataclasses import asdict

from models import ContextCompressionTrace, SummaryState
from services.research_store import SQLiteResearchStore


def test_context_compression_trace_round_trip_is_sanitized(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")
    state = SummaryState(research_topic="Compression tracing")
    state.context_compression_traces.append(
        ContextCompressionTrace(
            section_name="Task Context",
            original_estimated_size=50000,
            compressed_estimated_size=8000,
            strategy="semantic_head_tail",
            reason="section_exceeds_limit",
        )
    )

    loaded = store.get(store.save(state))

    assert loaded is not None
    assert len(loaded.context_compression_traces) == 1
    trace = loaded.context_compression_traces[0]
    assert asdict(trace) == {
        "section_name": "Task Context",
        "original_estimated_size": 50000,
        "compressed_estimated_size": 8000,
        "strategy": "semantic_head_tail",
        "reason": "section_exceeds_limit",
    }
    assert not hasattr(trace, "content")
    assert not hasattr(trace, "prompt")
    assert not hasattr(trace, "evidence")
