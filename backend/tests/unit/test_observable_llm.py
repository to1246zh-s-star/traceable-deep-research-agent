from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from hello_agents.core.exceptions import HelloAgentsException

from services.observable_llm import (
    LLMUsageCollector,
    ObservableHelloAgentsLLM,
)


def _usage(
    prompt: int,
    completion: int,
    total: int,
):
    return SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
    )


def _response(content="ok", choices_marker=None, usage=None):
    choices = (
        [SimpleNamespace(message=SimpleNamespace(content=content))]
        if choices_marker is None
        else choices_marker
    )
    return SimpleNamespace(choices=choices, usage=usage)


def _observable_with_responses(*responses):
    llm = object.__new__(ObservableHelloAgentsLLM)
    llm.model = "test-model"
    llm.temperature = 0.1
    llm.max_tokens = 100
    llm.usage_collector = LLMUsageCollector()
    create = Mock(side_effect=responses)
    llm._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)
        )
    )
    return llm, create


def test_usage_collector_accumulates_provider_usage():
    collector = LLMUsageCollector()

    collector.record_call(
        _usage(
            10,
            5,
            15,
        )
    )

    collector.record_call(
        _usage(
            20,
            7,
            27,
        )
    )

    result = collector.snapshot()

    assert result["call_count"] == 2
    assert result["calls_with_usage"] == 2
    assert result["prompt_tokens"] == 30
    assert result["completion_tokens"] == 12
    assert result["total_tokens"] == 42


def test_usage_collector_preserves_missing_usage():
    collector = LLMUsageCollector()

    collector.record_call(
        _usage(
            10,
            5,
            15,
        )
    )

    collector.record_call()

    result = collector.snapshot()

    assert result["call_count"] == 2
    assert result["calls_with_usage"] == 1


def test_usage_collector_reset():
    collector = LLMUsageCollector()

    collector.record_call(
        _usage(
            1,
            2,
            3,
        )
    )

    collector.reset()

    result = collector.snapshot()

    assert result["call_count"] == 0
    assert result["calls_with_usage"] == 0
    assert result["total_tokens"] is None


def test_invoke_retries_choices_none_then_succeeds(monkeypatch):
    monkeypatch.setattr("services.observable_llm.time.sleep", Mock())
    llm, create = _observable_with_responses(
        SimpleNamespace(choices=None, usage=None),
        _response(content="recovered"),
    )

    assert llm.invoke([{"role": "user", "content": "test"}]) == "recovered"
    assert create.call_count == 2


def test_invoke_retries_empty_choices_then_succeeds(monkeypatch):
    monkeypatch.setattr("services.observable_llm.time.sleep", Mock())
    llm, create = _observable_with_responses(
        _response(choices_marker=[]),
        _response(content="recovered"),
    )

    assert llm.invoke([{"role": "user", "content": "test"}]) == "recovered"
    assert create.call_count == 2


def test_invoke_exhausts_bounded_empty_response_retries(monkeypatch, caplog):
    sleep = Mock()
    monkeypatch.setattr("services.observable_llm.time.sleep", sleep)
    llm, create = _observable_with_responses(
        None,
        _response(choices_marker=[]),
        SimpleNamespace(choices=None, usage=None),
    )

    with pytest.raises(HelloAgentsException, match="provider response invalid"):
        llm.invoke([{"role": "user", "content": "test"}])

    assert create.call_count == 3
    assert sleep.call_count == 2
    assert "retry 1/2" in caplog.text
    assert "retry 2/2" in caplog.text
    assert "retries exhausted" in caplog.text


def test_invoke_does_not_retry_provider_exception(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("services.observable_llm.time.sleep", sleep)
    llm, create = _observable_with_responses(
        RuntimeError("401 invalid API key")
    )

    with pytest.raises(HelloAgentsException, match="401 invalid API key"):
        llm.invoke([{"role": "user", "content": "test"}])

    assert create.call_count == 1
    sleep.assert_not_called()


def test_invoke_normal_response_is_unchanged():
    llm, create = _observable_with_responses(_response(content="normal"))

    assert llm.invoke([{"role": "user", "content": "test"}]) == "normal"
    assert create.call_count == 1


def test_invoke_retry_usage_is_recorded_once_per_attempt(monkeypatch):
    monkeypatch.setattr("services.observable_llm.time.sleep", Mock())
    llm, _ = _observable_with_responses(
        _response(
            choices_marker=[],
            usage=_usage(2, 1, 3),
        ),
        _response(
            content="recovered",
            usage=_usage(10, 5, 15),
        ),
    )

    assert llm.invoke([{"role": "user", "content": "test"}]) == "recovered"
    assert llm.usage_snapshot() == {
        "call_count": 2,
        "calls_with_usage": 2,
        "prompt_tokens": 12,
        "completion_tokens": 6,
        "total_tokens": 18,
    }
