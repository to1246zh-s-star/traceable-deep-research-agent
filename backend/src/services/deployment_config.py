"""Deployment configuration validation without provider network probes."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit

from config import Configuration, SearchAPI


@dataclass(kw_only=True, frozen=True)
class DeploymentConfigStatus:
    """Safe, deterministic configuration-readiness result."""

    ready: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe status containing no configuration values."""
        return {
            "status": "ready" if self.ready else "not_ready",
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_deployment_config(
    config: Configuration,
    *,
    environment: Mapping[str, str] | None = None,
) -> DeploymentConfigStatus:
    """Validate configuration shape without contacting external services."""
    env = environment if environment is not None else os.environ
    errors: list[str] = []
    warnings: list[str] = []
    provider = (config.llm_provider or "").strip().lower()

    if provider not in {"ollama", "lmstudio", "custom"}:
        errors.append("LLM_PROVIDER is unsupported")
    elif provider == "custom":
        if not (config.llm_model_id or "").strip():
            errors.append("LLM_MODEL_ID is required for custom LLM_PROVIDER")
        if not (config.llm_base_url or "").strip():
            errors.append("LLM_BASE_URL is required for custom LLM_PROVIDER")
        elif not _is_http_endpoint(config.llm_base_url):
            errors.append("LLM_BASE_URL must be an HTTP(S) endpoint")
        if not (config.llm_api_key or "").strip():
            errors.append("LLM_API_KEY is required for custom LLM_PROVIDER")

    search_api = (
        config.search_api.value
        if isinstance(config.search_api, SearchAPI)
        else str(config.search_api).strip().lower()
    )
    required_search_secret = {
        SearchAPI.TAVILY.value: "TAVILY_API_KEY",
        SearchAPI.PERPLEXITY.value: "PERPLEXITY_API_KEY",
    }.get(search_api)
    if required_search_secret and not (env.get(required_search_secret) or "").strip():
        errors.append(f"{required_search_secret} is required for {search_api} search")

    db_path = (config.research_db_path or "").strip()
    if not db_path:
        errors.append("RESEARCH_DB_PATH must not be empty")
    elif "\x00" in db_path:
        errors.append("RESEARCH_DB_PATH contains an invalid character")
    elif db_path == ":memory:":
        warnings.append("RESEARCH_DB_PATH is non-persistent")

    return DeploymentConfigStatus(
        ready=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def safe_endpoint_for_log(value: str | None) -> str:
    """Return only a URL origin, excluding credentials, path, and query."""
    if not value or not value.strip():
        return "unset"
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.hostname:
        return "configured"
    try:
        parsed_port = parsed.port
    except ValueError:
        return "configured"
    port = f":{parsed_port}" if parsed_port is not None else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _is_http_endpoint(value: str) -> bool:
    """Return whether a configured endpoint has a safe HTTP URL shape."""
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        parsed.port
    except ValueError:
        return False
    return True
