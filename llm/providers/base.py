from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderCallContext:
    prompt_key: str
    prompt_version: str
    scenario: str
    expected_schema: str
    system_prompt: str
    temperature: float
    max_tokens: int | None


@dataclass(frozen=True)
class ProviderCallResult:
    text: str
    provider: str
    model: str | None
    prompt_key: str
    prompt_version: str
    scenario: str
    expected_schema: str
    latency_ms: int
    request_id: str | None
    token_usage: dict[str, int] | None
    retry_count: int
    success: bool
    error: str | None = None
    fallback_used: bool = False

    def to_trace_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_key": self.prompt_key,
            "prompt_version": self.prompt_version,
            "scenario": self.scenario,
            "expected_schema": self.expected_schema,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "token_usage": self.token_usage,
            "retry_count": self.retry_count,
            "success": self.success,
            "error": self.error,
            "fallback_used": self.fallback_used,
        }


class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str, *, context: ProviderCallContext) -> ProviderCallResult: ...
