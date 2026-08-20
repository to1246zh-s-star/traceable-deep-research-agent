import pytest

from services.llm_preflight import (
    LLMPreflightGuard,
    classify_llm_exception,
)


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_successful_probe_is_cached():
    clock = FakeClock()
    calls = []

    guard = LLMPreflightGuard(
        success_ttl_seconds=60.0,
        failure_ttl_seconds=15.0,
        clock=clock,
    )

    def probe():
        calls.append("called")
        return "OK"

    first = guard.check(probe)
    second = guard.check(probe)

    assert first.available is True
    assert first.code == "ok"

    assert second == first
    assert len(calls) == 1


def test_success_cache_expires():
    clock = FakeClock()
    calls = []

    guard = LLMPreflightGuard(
        success_ttl_seconds=10.0,
        clock=clock,
    )

    def probe():
        calls.append("called")

    guard.check(probe)

    clock.advance(11.0)

    guard.check(probe)

    assert len(calls) == 2


def test_failed_probe_is_cached_briefly():
    clock = FakeClock()
    calls = []

    guard = LLMPreflightGuard(
        failure_ttl_seconds=15.0,
        clock=clock,
    )

    def probe():
        calls.append("called")
        raise RuntimeError(
            "429 insufficient balance"
        )

    first = guard.check(probe)
    second = guard.check(probe)

    assert first.available is False
    assert first.code == "llm_quota_exhausted"
    assert first.reason == "insufficient_balance"

    assert second == first
    assert len(calls) == 1


def test_failure_cache_expires_and_retries():
    clock = FakeClock()
    calls = []

    guard = LLMPreflightGuard(
        failure_ttl_seconds=5.0,
        clock=clock,
    )

    def probe():
        calls.append("called")

        if len(calls) == 1:
            raise RuntimeError(
                "429 insufficient balance"
            )

        return "OK"

    first = guard.check(probe)

    assert first.available is False

    clock.advance(6.0)

    second = guard.check(probe)

    assert second.available is True
    assert len(calls) == 2


def test_invalidate_forces_new_probe():
    calls = []

    guard = LLMPreflightGuard()

    def probe():
        calls.append("called")

    guard.check(probe)
    guard.invalidate()
    guard.check(probe)

    assert len(calls) == 2


@pytest.mark.parametrize(
    ("message", "code", "reason"),
    [
        (
            "Error code: 429 - insufficient balance",
            "llm_quota_exhausted",
            "insufficient_balance",
        ),
        (
            "429 Too Many Requests",
            "llm_rate_limited",
            "rate_limited",
        ),
        (
            "RateLimitError",
            "llm_rate_limited",
            "rate_limited",
        ),
        (
            "401 Unauthorized",
            "llm_authentication_failed",
            "authentication_failed",
        ),
        (
            "invalid_api_key",
            "llm_authentication_failed",
            "authentication_failed",
        ),
        (
            "request timed out",
            "llm_timeout",
            "timeout",
        ),
        (
            "connection reset by peer",
            "llm_unavailable",
            "provider_error",
        ),
    ],
)
def test_exception_classification(
    message,
    code,
    reason,
):
    result = classify_llm_exception(
        RuntimeError(message)
    )

    assert result.available is False
    assert result.code == code
    assert result.reason == reason


def test_invalid_ttl_rejected():
    with pytest.raises(ValueError):
        LLMPreflightGuard(
            success_ttl_seconds=-1,
        )

    with pytest.raises(ValueError):
        LLMPreflightGuard(
            failure_ttl_seconds=-1,
        )
