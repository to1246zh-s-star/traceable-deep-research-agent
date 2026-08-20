from fastapi.testclient import TestClient

import main
from services.llm_preflight import (
    LLMPreflightResult,
)


class FakeAgent:
    def __init__(self, config):
        self.config = config
        self.last_state = None


def test_research_returns_503_when_llm_quota_exhausted(
    monkeypatch,
):
    app = main.create_app()

    monkeypatch.setattr(
        main,
        "DeepResearchAgent",
        FakeAgent,
    )

    def fake_check(probe):
        return LLMPreflightResult(
            available=False,
            code="llm_quota_exhausted",
            reason="insufficient_balance",
        )

    app.state.llm_preflight_guard.check = fake_check

    client = TestClient(app)

    response = client.post(
        "/research",
        json={
            "topic": "Compare Qdrant and Milvus.",
        },
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": {
            "code": "llm_quota_exhausted",
            "reason": "insufficient_balance",
            "provider": "custom",
        }
    }


def test_stream_returns_503_before_sse_starts_when_llm_unavailable(
    monkeypatch,
):
    app = main.create_app()

    monkeypatch.setattr(
        main,
        "DeepResearchAgent",
        FakeAgent,
    )

    def fake_check(probe):
        return LLMPreflightResult(
            available=False,
            code="llm_rate_limited",
            reason="rate_limited",
        )

    app.state.llm_preflight_guard.check = fake_check

    client = TestClient(app)

    response = client.post(
        "/research/stream",
        json={
            "topic": "Compare Qdrant and Milvus.",
        },
    )

    assert response.status_code == 503

    assert response.headers[
        "content-type"
    ].startswith(
        "application/json"
    )

    assert response.json()["detail"] == {
        "code": "llm_rate_limited",
        "reason": "rate_limited",
        "provider": "custom",
    }


def test_llm_error_detail_does_not_expose_raw_provider_message():
    result = LLMPreflightResult(
        available=False,
        code="llm_quota_exhausted",
        reason="insufficient_balance",
    )

    detail = main._llm_unavailable_detail(
        result,
        provider="custom",
    )

    serialized = str(detail)

    assert "api_key" not in serialized
    assert "request_id" not in serialized
    assert "chat/completions" not in serialized
