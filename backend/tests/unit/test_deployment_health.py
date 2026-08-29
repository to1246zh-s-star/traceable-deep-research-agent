from fastapi.testclient import TestClient

import main


def test_health_is_liveness_and_never_calls_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("SEARCH_API", "duckduckgo")
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "health.db"))

    def unexpected_preflight(*args, **kwargs):
        raise AssertionError("health must not call provider preflight")

    monkeypatch.setattr(main.LLMPreflightGuard, "check", unexpected_preflight)
    app = main.create_app()

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_config_only_without_echoing_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL_ID", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("SEARCH_API", "duckduckgo")
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "ready.db"))

    app = main.create_app()
    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert "LLM_API_KEY is required for custom LLM_PROVIDER" in payload["errors"]
    assert "api_key=" not in response.text.lower()


def test_configured_database_path_initializes_persistent_store(monkeypatch, tmp_path):
    db_path = tmp_path / "nested" / "research.db"
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("RESEARCH_DB_PATH", str(db_path))

    main.create_app()

    assert db_path.is_file()
