from __future__ import annotations

import json

import httpx

from llm.openai_compatible_client import OpenAICompatibleClient
from llm.types import LLMRequest


def test_openai_compatible_client_complete_works_with_base_url_without_v1() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["stream"] is False
        assert payload["model"] == "qwen3.5:9b"
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "处理完成"}}
                ]
            },
        )

    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:11434",
        api_key="ollama-local",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    output = client.complete(
        LLMRequest(
            model="qwen3.5:9b",
            prompt="请总结工单",
            system_prompt="你是客服助手",
            temperature=0.2,
            max_tokens=256,
        )
    )
    assert output == "处理完成"


def test_openai_compatible_client_stream_complete_parses_sse() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["stream"] is True
        stream_body = (
            'data: {"choices":[{"delta":{"content":"已"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"收到"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            status_code=200,
            content=stream_body.encode("utf-8"),
            headers={"Content-Type": "text/event-stream"},
        )

    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama-local",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    tokens = list(
        client.stream_complete(
            LLMRequest(
                model="qwen3.5:9b",
                prompt="回复用户",
                system_prompt="你是客服助手",
                temperature=0.2,
                max_tokens=None,
            )
        )
    )
    assert "".join(tokens) == "已收到"


def test_openai_compatible_client_complete_with_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"x-request-id": "req-test-123"},
            json={
                "id": "chatcmpl-abc",
                "model": "qwen3.5:9b",
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20,
                },
                "choices": [
                    {"message": {"role": "assistant", "content": "摘要生成成功"}},
                ],
            },
        )

    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama-local",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    response = client.complete_with_metadata(
        LLMRequest(
            model="qwen3.5:9b",
            prompt="请总结工单",
            system_prompt="你是客服助手",
            temperature=0.2,
            max_tokens=128,
        )
    )

    assert response.text == "摘要生成成功"
    assert response.request_id == "req-test-123"
    assert response.model == "qwen3.5:9b"
    assert response.token_usage is not None
    assert response.token_usage.total_tokens == 20
