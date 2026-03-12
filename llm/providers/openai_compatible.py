from __future__ import annotations

import time
from collections.abc import Callable

from llm.types import LLMResponse

from .base import LLMProvider, ProviderCallContext, ProviderCallResult


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        *,
        name: str = "openai_compatible",
        model: str,
        timeout_seconds: float,
        temperature: float,
        max_tokens: int | None,
        retry_count: int,
        call_fn: Callable[..., LLMResponse],
    ) -> None:
        self.name = name
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._retry_count = max(0, retry_count)
        self._call_fn = call_fn

    def complete(self, prompt: str, *, context: ProviderCallContext) -> ProviderCallResult:
        start = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self._retry_count + 1):
            try:
                response: LLMResponse = self._call_fn(
                    prompt=prompt,
                    model=self._model,
                    system_prompt=context.system_prompt,
                    temperature=context.temperature,
                    max_tokens=context.max_tokens,
                    timeout_seconds=self._timeout_seconds,
                )
                latency_ms = int((time.perf_counter() - start) * 1000)
                return ProviderCallResult(
                    text=response.text,
                    provider=self.name,
                    model=response.model or self._model,
                    prompt_key=context.prompt_key,
                    prompt_version=context.prompt_version,
                    scenario=context.scenario,
                    expected_schema=context.expected_schema,
                    latency_ms=latency_ms,
                    request_id=response.request_id,
                    token_usage=response.token_usage.as_dict() if response.token_usage else None,
                    retry_count=attempt,
                    success=True,
                    error=None,
                )
            except Exception as exc:  # pragma: no cover - network/runtime failures
                last_error = exc
                continue

        latency_ms = int((time.perf_counter() - start) * 1000)
        raise RuntimeError(
            f"OpenAI-compatible provider failed after {self._retry_count + 1} attempts "
            f"(latency_ms={latency_ms}): {last_error}"
        )
