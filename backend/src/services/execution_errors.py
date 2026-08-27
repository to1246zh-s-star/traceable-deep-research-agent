"""Stable business-level classification for executor exceptions."""

from __future__ import annotations


def classify_execution_error(error: Exception) -> str:
    """Map provider-specific exceptions to stable executor error categories."""

    message = str(error).strip().lower()
    error_name = type(error).__name__.lower()
    combined = f"{error_name} {message}"

    if isinstance(error, TimeoutError) or any(
        marker in combined
        for marker in (
            "timeout",
            "timed out",
            "read timeout",
            "connect timeout",
        )
    ):
        return "timeout"

    # Check quota/balance BEFORE generic 429 classification.
    # Some providers return HTTP 429 for exhausted account balance.
    if any(
        marker in combined
        for marker in (
            "quota exceeded",
            "exceeded today's quota",
            "exceeded today",
            "insufficient quota",
            "daily quota",
            "insufficient balance",
            "insufficient_balance",
            "insufficient credit",
            "insufficient credits",
            "account balance",
        )
    ):
        return "quota_exceeded"

    if any(
        marker in combined
        for marker in (
            "rate limit",
            "rate_limit",
            "rate-limit",
            "too many requests",
            "429",
        )
    ):
        return "rate_limited"

    if any(
        marker in combined
        for marker in (
            "unauthorized",
            "authentication",
            "invalid api key",
            "api key invalid",
            "missing api key",
            "permission denied",
            "401",
            "403",
        )
    ):
        return "authentication"

    if any(
        marker in combined
        for marker in (
            "service unavailable",
            "provider unavailable",
            "connection refused",
            "connection reset",
            "connection error",
            "503",
        )
    ):
        return "provider_unavailable"

    if isinstance(error, RuntimeError):
        return "provider_error"

    return "unknown_error"
