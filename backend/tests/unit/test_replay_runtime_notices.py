from main import _build_research_replay
from models import SummaryState


def test_replay_exposes_runtime_notices():
    state = SummaryState(
        research_topic="A vs B",
        runtime_notices=[
            {
                "stage": "integration_assessment",
                "error_type": "quota_exceeded",
                "message": "insufficient balance",
                "degraded": True,
            }
        ],
    )

    replay = _build_research_replay(
        "research_notice",
        state,
    )

    assert replay[
        "runtime_notices"
    ] == [
        {
            "stage": "integration_assessment",
            "error_type": "quota_exceeded",
            "message": "insufficient balance",
            "degraded": True,
        }
    ]
