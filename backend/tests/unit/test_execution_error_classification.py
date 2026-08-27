from services.execution_errors import classify_execution_error


class AuthenticationProviderError(Exception):
    pass


class RateLimitProviderError(Exception):
    pass


class UnknownCustomError(Exception):
    pass


def test_timeout_error_is_classified_as_timeout() -> None:
    error = TimeoutError("search timed out")

    assert classify_execution_error(error) == "timeout"


def test_unauthorized_message_is_classified_as_authentication() -> None:
    error = AuthenticationProviderError(
        "401 Unauthorized: invalid API key"
    )

    assert classify_execution_error(error) == "authentication"


def test_quota_message_is_classified_as_quota_exceeded() -> None:
    error = RuntimeError(
        "You have exceeded today's quota"
    )

    assert classify_execution_error(error) == "quota_exceeded"


def test_rate_limit_message_is_classified_as_rate_limited() -> None:
    error = RateLimitProviderError(
        "429 Too Many Requests: rate limit exceeded"
    )

    assert classify_execution_error(error) == "rate_limited"


def test_runtime_error_is_classified_as_provider_error() -> None:
    error = RuntimeError(
        "search provider returned an invalid response"
    )

    assert classify_execution_error(error) == "provider_error"


def test_unknown_exception_is_classified_as_unknown_error() -> None:
    error = UnknownCustomError(
        "unexpected executor failure"
    )

    assert classify_execution_error(error) == "unknown_error"


def test_classifies_insufficient_balance_as_quota_exceeded():
    error = RuntimeError(
        "Error code: 429 - "
        "{'error': {'message': 'insufficient balance'}}"
    )

    assert (
        classify_execution_error(error)
        == "quota_exceeded"
    )


def test_classifies_model_rate_limit_as_rate_limited():
    error = RuntimeError(
        "Error code: 429 - We have to rate limit "
        "you for model Qwen"
    )

    assert (
        classify_execution_error(error)
        == "rate_limited"
    )


def test_classifies_service_unavailable():
    error = RuntimeError(
        "503 service unavailable"
    )

    assert (
        classify_execution_error(error)
        == "provider_unavailable"
    )
