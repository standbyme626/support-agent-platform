from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMRequest:
    model: str
    prompt: str
    system_prompt: str
    temperature: float
    max_tokens: int | None

