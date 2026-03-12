from __future__ import annotations

import pytest

from llm.providers.base import ProviderCallContext, ProviderCallResult
from llm.providers.fallback_router import ProviderExhaustedError, ProviderFallbackRouter


class _FailingProvider:
    name = "primary"

    def complete(self, prompt: str, *, context: ProviderCallContext) -> ProviderCallResult:
        _ = prompt
        _ = context
        raise RuntimeError("upstream timeout")


class _SuccessProvider:
    name = "backup"

    def complete(self, prompt: str, *, context: ProviderCallContext) -> ProviderCallResult:
        return ProviderCallResult(
            text=f"[backup] {prompt}",
            provider=self.name,
            model="qwen3.5:9b",
            prompt_key=context.prompt_key,
            prompt_version=context.prompt_version,
            scenario=context.scenario,
            expected_schema=context.expected_schema,
            latency_ms=12,
            request_id="req-fallback",
            token_usage={"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
            retry_count=0,
            success=True,
            error=None,
            fallback_used=False,
        )


def _context() -> ProviderCallContext:
    return ProviderCallContext(
        prompt_key="case_summary",
        prompt_version="v1",
        scenario="case_copilot",
        expected_schema="text/plain",
        system_prompt="你是客服助手",
        temperature=0.2,
        max_tokens=256,
    )


def test_fallback_router_uses_backup_provider_when_primary_fails() -> None:
    router = ProviderFallbackRouter([_FailingProvider(), _SuccessProvider()])
    result = router.complete("工单摘要", context=_context())

    assert result.provider == "backup"
    assert result.success is True
    assert result.fallback_used is True


def test_fallback_router_raises_when_all_providers_fail() -> None:
    router = ProviderFallbackRouter([_FailingProvider()])
    with pytest.raises(ProviderExhaustedError) as exc:
        router.complete("工单摘要", context=_context())
    assert "primary" in str(exc.value)
