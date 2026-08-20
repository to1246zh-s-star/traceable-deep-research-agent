"""Lightweight cached availability checks for the configured LLM."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class LLMPreflightResult:
    available: bool
    code: str
    reason: str


class LLMPreflightGuard:
    """
    Cache short-lived LLM availability checks.

    This is intentionally a runtime/API concern rather than research-domain
    state. Successful and failed checks are both cached briefly to avoid
    adding one extra LLM request to every research call.
    """

    def __init__(
        self,
        *,
        success_ttl_seconds: float = 60.0,
        failure_ttl_seconds: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if success_ttl_seconds < 0:
            raise ValueError(
                "success_ttl_seconds must be non-negative"
            )

        if failure_ttl_seconds < 0:
            raise ValueError(
                "failure_ttl_seconds must be non-negative"
            )

        self._success_ttl_seconds = success_ttl_seconds
        self._failure_ttl_seconds = failure_ttl_seconds
        self._clock = clock

        self._cached_result: LLMPreflightResult | None = None
        self._expires_at = 0.0

    def check(
        self,
        probe: Callable[[], object],
    ) -> LLMPreflightResult:
        """Return cached availability or execute one lightweight probe."""

        now = self._clock()

        if (
            self._cached_result is not None
            and now < self._expires_at
        ):
            return self._cached_result

        try:
            probe()
        except Exception as exc:
            result = classify_llm_exception(exc)
            ttl = self._failure_ttl_seconds
        else:
            result = LLMPreflightResult(
                available=True,
                code="ok",
                reason="available",
            )
            ttl = self._success_ttl_seconds

        self._cached_result = result
        self._expires_at = now + ttl

        return result

    def invalidate(self) -> None:
        """Force the next request to execute a fresh probe."""

        self._cached_result = None
        self._expires_at = 0.0


def classify_llm_exception(
    exc: Exception,
) -> LLMPreflightResult:
    """
    Convert provider/SDK exceptions into safe public error categories.

    Raw exception text is inspected only for classification and is never
    intended to be returned directly to API clients.
    """

    text = str(exc).casefold()

    if (
        "insufficient balance" in text
        or "insufficient_balance" in text
    ):
        return LLMPreflightResult(
            available=False,
            code="llm_quota_exhausted",
            reason="insufficient_balance",
        )

    if (
        "429" in text
        or "rate limit" in text
        or "ratelimit" in text
    ):
        return LLMPreflightResult(
            available=False,
            code="llm_rate_limited",
            reason="rate_limited",
        )

    if (
        "401" in text
        or "403" in text
        or "unauthorized" in text
        or "authentication" in text
        or "invalid api key" in text
        or "invalid_api_key" in text
    ):
        return LLMPreflightResult(
            available=False,
            code="llm_authentication_failed",
            reason="authentication_failed",
        )

    if (
        "timeout" in text
        or "timed out" in text
    ):
        return LLMPreflightResult(
            available=False,
            code="llm_timeout",
            reason="timeout",
        )

    return LLMPreflightResult(
        available=False,
        code="llm_unavailable",
        reason="provider_error",
    )
