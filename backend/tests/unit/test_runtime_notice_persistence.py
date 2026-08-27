from models import SummaryState
from services.research_store import (
    _deserialize_v3_state,
    _serialize_v3_state,
)


def test_runtime_notices_round_trip_through_v3_state():
    state = SummaryState(
        research_topic="test",
        runtime_notices=[
            {
                "stage": "report_generation",
                "error_type": "rate_limited",
                "message": "429 rate limit",
                "degraded": True,
                "metadata": {
                    "fallback": "deterministic",
                },
            }
        ],
    )

    raw = _serialize_v3_state(
        state
    )

    restored = _deserialize_v3_state(
        raw
    )

    assert restored[
        "runtime_notices"
    ] == state.runtime_notices
