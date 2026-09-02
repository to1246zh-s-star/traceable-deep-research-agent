"""Observable HelloAgents LLM with provider-level usage accounting."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from threading import Lock
from typing import Any

from hello_agents import HelloAgentsLLM
from hello_agents.core.exceptions import HelloAgentsException

logger = logging.getLogger(__name__)


class _MalformedProviderResponse(Exception):
    """Indicate a completed provider call without usable message content."""


class LLMUsageCollector:
    """Thread-safe usage accumulator for one Agent run."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", Lock()):
            self.call_count = 0
            self.calls_with_usage = 0
            self.prompt_tokens: int | None = None
            self.completion_tokens: int | None = None
            self.total_tokens: int | None = None

    @staticmethod
    def _usage_value(
        usage: Any,
        name: str,
    ) -> int | None:
        if usage is None:
            return None

        value = getattr(
            usage,
            name,
            None,
        )

        if value is None and isinstance(
            usage,
            dict,
        ):
            value = usage.get(name)

        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return max(0, value)

        return None

    def record_call(
        self,
        usage: Any = None,
    ) -> None:
        prompt = self._usage_value(
            usage,
            "prompt_tokens",
        )

        completion = self._usage_value(
            usage,
            "completion_tokens",
        )

        total = self._usage_value(
            usage,
            "total_tokens",
        )

        with self._lock:
            self.call_count += 1

            if (
                prompt is not None
                or completion is not None
                or total is not None
            ):
                self.calls_with_usage += 1

            if prompt is not None:
                self.prompt_tokens = (
                    (self.prompt_tokens or 0)
                    + prompt
                )

            if completion is not None:
                self.completion_tokens = (
                    (self.completion_tokens or 0)
                    + completion
                )

            if total is not None:
                self.total_tokens = (
                    (self.total_tokens or 0)
                    + total
                )

    def snapshot(
        self,
    ) -> dict[str, int | None]:
        with self._lock:
            return {
                "call_count": self.call_count,
                "calls_with_usage":
                    self.calls_with_usage,
                "prompt_tokens":
                    self.prompt_tokens,
                "completion_tokens":
                    self.completion_tokens,
                "total_tokens":
                    self.total_tokens,
            }


class ObservableHelloAgentsLLM(
    HelloAgentsLLM
):
    """HelloAgentsLLM preserving provider usage observations."""

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            *args,
            **kwargs,
        )

        self.usage_collector = (
            LLMUsageCollector()
        )

    def reset_usage(self) -> None:
        self.usage_collector.reset()

    def usage_snapshot(
        self,
    ) -> dict[str, int | None]:
        return (
            self.usage_collector.snapshot()
        )

    def invoke(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Non-streaming call with exact provider usage capture."""
        max_retries = 2

        for attempt in range(max_retries + 1):
            response = None

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=kwargs.get(
                        "temperature",
                        self.temperature,
                    ),
                    max_tokens=kwargs.get(
                        "max_tokens",
                        self.max_tokens,
                    ),
                    **{
                        key: value
                        for key, value
                        in kwargs.items()
                        if key not in {
                            "temperature",
                            "max_tokens",
                        }
                    },
                )

                choices = getattr(response, "choices", None)
                if not choices:
                    raise _MalformedProviderResponse(
                        "provider response has no choices"
                    )

                first_choice = choices[0]
                message = getattr(first_choice, "message", None)
                content = getattr(message, "content", None)
                if first_choice is None or message is None or content is None:
                    raise _MalformedProviderResponse(
                        "provider response has no message content"
                    )

                self.usage_collector.record_call(
                    getattr(response, "usage", None)
                )
                return content

            except _MalformedProviderResponse as exc:
                # Count each outbound attempt once. Preserve provider usage
                # only when the response supplied it.
                self.usage_collector.record_call(
                    getattr(response, "usage", None)
                )

                if attempt < max_retries:
                    logger.warning(
                        "Provider empty response -> retry %s/%s",
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(0.1 * (attempt + 1))
                    continue

                logger.error(
                    "Provider empty response retries exhausted"
                )
                raise HelloAgentsException(
                    f"LLM provider response invalid: {exc}"
                ) from exc

            except Exception as exc:
                # Provider exceptions are not empty responses; authentication,
                # configuration, and request errors must fail promptly.
                self.usage_collector.record_call()
                raise HelloAgentsException(
                    f"LLM调用失败: {str(exc)}"
                ) from exc

        raise AssertionError("unreachable")

    def stream_invoke(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Iterator[str]:
        """Streaming call with provider-reported usage when supported."""

        temperature = kwargs.get(
            "temperature",
            self.temperature,
        )

        request_kwargs = {
            key: value
            for key, value
            in kwargs.items()
            if key not in {
                "temperature",
                "max_tokens",
            }
        }

        try:
            response = (
                self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=kwargs.get(
                        "max_tokens",
                        self.max_tokens,
                    ),
                    stream=True,
                    stream_options={
                        "include_usage": True,
                    },
                    **request_kwargs,
                )
            )

            usage = None

            for chunk in response:
                chunk_usage = getattr(
                    chunk,
                    "usage",
                    None,
                )

                if chunk_usage is not None:
                    usage = chunk_usage

                choices = getattr(
                    chunk,
                    "choices",
                    None,
                ) or []

                if not choices:
                    continue

                delta = choices[0].delta
                content = (
                    getattr(
                        delta,
                        "content",
                        None,
                    )
                    or ""
                )

                if content:
                    yield content

            self.usage_collector.record_call(
                usage
            )

        except Exception as exc:
            self.usage_collector.record_call()

            raise HelloAgentsException(
                f"LLM调用失败: {str(exc)}"
            )
