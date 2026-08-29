from types import SimpleNamespace

from services.observable_llm import (
    LLMUsageCollector,
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
