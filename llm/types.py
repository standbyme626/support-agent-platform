from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMRequest:
    model: str
    prompt: str
    system_prompt: str
    temperature: float
    max_tokens: int | None


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def as_dict(self) -> dict[str, int]:
        payload: dict[str, int] = {}
        if self.prompt_tokens is not None:
            payload["prompt_tokens"] = self.prompt_tokens
        if self.completion_tokens is not None:
            payload["completion_tokens"] = self.completion_tokens
        if self.total_tokens is not None:
            payload["total_tokens"] = self.total_tokens
        return payload


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str | None
    request_id: str | None
    token_usage: LLMUsage | None
    raw_payload: dict[str, Any] | None = None
