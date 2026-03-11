from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from .types import LLMRequest


class OpenAICompatibleClient:
    """Small OpenAI-compatible client for both local and cloud providers."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def complete(self, request: LLMRequest) -> str:
        payload = _build_payload(request=request, stream=False)
        with httpx.Client(timeout=self._timeout_seconds, transport=self._transport) as client:
            response = client.post(
                _chat_completions_url(self._base_url),
                headers=_build_headers(self._api_key),
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        return _extract_text_from_completion(data)

    def stream_complete(self, request: LLMRequest) -> Iterator[str]:
        payload = _build_payload(request=request, stream=True)
        with httpx.Client(timeout=self._timeout_seconds, transport=self._transport) as client:
            with client.stream(
                "POST",
                _chat_completions_url(self._base_url),
                headers=_build_headers(self._api_key),
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    event_data = line[5:].strip()
                    if event_data == "[DONE]":
                        break
                    chunk = json.loads(event_data)
                    delta = (
                        chunk.get("choices", [{}])[0].get("delta", {})
                        if isinstance(chunk, dict)
                        else {}
                    )
                    token = _extract_text_token(delta.get("content"))
                    if token:
                        yield token


def _build_payload(*, request: LLMRequest, stream: bool) -> dict[str, Any]:
    payload = {
        "model": request.model,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.prompt},
        ],
        "temperature": request.temperature,
        "stream": stream,
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    return payload


def _build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _extract_text_from_completion(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"Invalid completion payload: {asdict_error(payload)}")
    message = choices[0].get("message", {})
    content = message.get("content")
    text = _extract_text_token(content)
    if not text:
        raise RuntimeError("Completion payload has empty assistant content")
    return text


def _extract_text_token(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def asdict_error(payload: dict[str, Any]) -> dict[str, Any]:
    return {"keys": sorted(payload.keys())[:20]}
