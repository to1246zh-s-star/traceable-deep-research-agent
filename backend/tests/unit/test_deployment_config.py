import pytest
from pydantic import ValidationError

from config import Configuration, SearchAPI
from services.deployment_config import (
    safe_endpoint_for_log,
    validate_deployment_config,
)


def test_complete_custom_provider_configuration_is_ready():
    config = Configuration(
        llm_provider="custom",
        llm_base_url="https://provider.example/v1",
        llm_model_id="model-a",
        llm_api_key="secret",
        search_api=SearchAPI.DUCKDUCKGO,
        research_db_path="./data/research.db",
    )

    status = validate_deployment_config(config, environment={})

    assert status.ready is True
    assert not status.errors


def test_missing_custom_provider_settings_are_configuration_errors():
    config = Configuration(
        llm_provider="custom",
        llm_base_url=None,
        llm_model_id=None,
        llm_api_key=None,
    )

    status = validate_deployment_config(config, environment={})

    assert status.ready is False
    assert "LLM_MODEL_ID is required for custom LLM_PROVIDER" in status.errors
    assert "LLM_BASE_URL is required for custom LLM_PROVIDER" in status.errors
    assert "LLM_API_KEY is required for custom LLM_PROVIDER" in status.errors
    assert "secret" not in repr(status)


def test_tavily_requires_key_but_duckduckgo_does_not():
    tavily = Configuration(llm_provider="ollama", search_api=SearchAPI.TAVILY)
    duckduckgo = Configuration(
        llm_provider="ollama",
        search_api=SearchAPI.DUCKDUCKGO,
    )

    assert validate_deployment_config(tavily, environment={}).ready is False
    assert validate_deployment_config(
        tavily,
        environment={"TAVILY_API_KEY": "configured"},
    ).ready is True
    assert validate_deployment_config(duckduckgo, environment={}).ready is True


def test_invalid_or_nonpersistent_database_paths_are_explicit():
    invalid = Configuration(llm_provider="ollama", research_db_path=" ")
    memory = Configuration(llm_provider="ollama", research_db_path=":memory:")

    assert validate_deployment_config(invalid, environment={}).ready is False
    memory_status = validate_deployment_config(memory, environment={})
    assert memory_status.ready is True
    assert memory_status.warnings == ("RESEARCH_DB_PATH is non-persistent",)


def test_safe_endpoint_logging_removes_all_secret_material():
    endpoint = safe_endpoint_for_log(
        "https://user:password@provider.example:8443/v1?api_key=secret#token"
    )

    assert endpoint == "https://provider.example:8443"
    assert "password" not in endpoint
    assert "api_key" not in endpoint
    assert "secret" not in endpoint
    assert "token" not in endpoint


def test_invalid_numeric_limits_are_rejected_by_configuration():
    with pytest.raises(ValidationError):
        Configuration(max_web_research_loops=0)


def test_invalid_custom_endpoint_is_not_ready_or_logged_verbatim():
    config = Configuration(
        llm_provider="custom",
        llm_base_url="https://provider.example:not-a-port/secret",
        llm_model_id="model-a",
        llm_api_key="secret",
    )

    status = validate_deployment_config(config, environment={})

    assert status.ready is False
    assert "LLM_BASE_URL must be an HTTP(S) endpoint" in status.errors
    assert safe_endpoint_for_log(config.llm_base_url) == "configured"
