from dataclasses import asdict

from models import SummaryState
from services.context_compression_trace import (
    build_context_compression_traces,
    record_context_compression_traces,
)
from services.context_engineering import ContextCompressor, ContextSection, ContextSelection


def _result():
    return ContextCompressor().compress(
        ContextSelection(
            purpose="test",
            sections=(ContextSection(name="Secret", content="sensitive-body-" * 100),),
        ),
        max_section_units=200,
    )


def test_compression_trace_is_sanitized_and_explicit():
    traces = build_context_compression_traces(_result())

    assert len(traces) == 1
    assert set(asdict(traces[0])) == {
        "section_name",
        "original_estimated_size",
        "compressed_estimated_size",
        "strategy",
        "reason",
    }
    assert "sensitive-body" not in repr(traces)
    assert traces[0].compressed_estimated_size < traces[0].original_estimated_size


def test_record_compression_trace_only_updates_observability():
    state = SummaryState(research_topic="unchanged")

    traces = record_context_compression_traces(state, _result())

    assert state.research_topic == "unchanged"
    assert state.context_compression_traces == traces
