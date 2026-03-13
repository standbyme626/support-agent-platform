from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Any

from config import LLMConfig

from .openai_compatible_client import OpenAICompatibleClient
from .providers.base import LLMProvider, ProviderCallContext
from .providers.fallback_router import ProviderExhaustedError, ProviderFallbackRouter
from .providers.openai_compatible import OpenAICompatibleProvider
from .tracing.prompt_registry import PromptRegistry, load_prompt_registry
from .types import LLMRequest, LLMResponse

DEFAULT_SYSTEM_PROMPT = "你是客服工单系统的助手，输出简洁、准确、可执行。"
PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class LLMManager:
    config: LLMConfig
    client: OpenAICompatibleClient

    @classmethod
    def from_config(cls, config: LLMConfig) -> LLMManager:
        client = OpenAICompatibleClient(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
        )
        return cls(config=config, client=client)

    def generate(self, prompt: str, *, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> str:
        return self.generate_with_metadata(
            prompt=prompt,
            model=self.config.model,
            system_prompt=system_prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout_seconds=self.config.timeout_seconds,
        ).text

    def generate_with_metadata(
        self,
        *,
        prompt: str,
        model: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int | None,
        timeout_seconds: float,
    ) -> LLMResponse:
        request = LLMRequest(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Timeout is configured on the client level today; keep method signature to
        # preserve future per-request timeout override compatibility.
        _ = timeout_seconds
        return self.client.complete_with_metadata(request)


class LLMGenerationError(RuntimeError):
    def __init__(self, message: str, *, trace_metadata: dict[str, Any]) -> None:
        super().__init__(message)
        self.trace_metadata = trace_metadata


class LLMModelAdapter:
    """Prompt-versioned adapter backed by provider router with trace metadata."""

    def __init__(
        self,
        *,
        router: ProviderFallbackRouter,
        prompt_registry: PromptRegistry,
        default_model: str,
        temperature: float,
        max_tokens: int | None,
        default_prompt_versions: dict[str, str] | None = None,
    ) -> None:
        self._router = router
        self._prompt_registry = prompt_registry
        self._default_model = default_model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._default_prompt_versions = dict(default_prompt_versions or {})

    def generate(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
    ) -> str:
        text, _ = self.generate_with_trace(
            task,
            variables,
            preferred_provider=preferred_provider,
        )
        return text

    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> tuple[str, dict[str, Any]]:
        resolved_version = prompt_version or self._default_prompt_versions.get(task)
        prompt_def = self._prompt_registry.resolve(task, version=resolved_version)
        rendered_prompt = self._render(prompt_def.template, variables)
        context = ProviderCallContext(
            prompt_key=prompt_def.prompt_key,
            prompt_version=prompt_def.prompt_version,
            scenario=prompt_def.scenario,
            expected_schema=prompt_def.expected_schema,
            system_prompt=system_prompt,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        try:
            result = self._router.complete(
                rendered_prompt,
                context=context,
                preferred_provider=preferred_provider,
            )
        except ProviderExhaustedError as exc:
            trace_metadata = {
                "provider": preferred_provider or "openai_compatible",
                "model": self._default_model,
                "prompt_key": prompt_def.prompt_key,
                "prompt_version": prompt_def.prompt_version,
                "scenario": prompt_def.scenario,
                "expected_schema": prompt_def.expected_schema,
                "latency_ms": 0,
                "request_id": f"failed-{prompt_def.prompt_key}-{prompt_def.prompt_version}",
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
                "retry_count": 0,
                "success": False,
                "error": str(exc),
                "fallback_used": True,
                "degraded": True,
            }
            raise LLMGenerationError("All providers failed", trace_metadata=trace_metadata) from exc
        metadata = result.to_trace_metadata()
        metadata["degraded"] = bool(metadata.get("fallback_used")) or not bool(
            metadata.get("success")
        )
        return result.text, metadata

    @staticmethod
    def _render(template: str, variables: dict[str, str]) -> str:
        expected_vars = {
            field_name
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name is not None
        }
        missing = expected_vars - set(variables)
        if missing:
            raise ValueError(f"Missing variables for template render: {sorted(missing)}")
        return template.format(**variables)


def build_summary_model_adapter(config: LLMConfig) -> LLMModelAdapter | None:
    if not config.enabled:
        return None
    if config.provider != "openai_compatible":
        raise ValueError(f"Unsupported LLM provider: {config.provider}")

    manager = LLMManager.from_config(config)
    providers: list[LLMProvider] = [
        OpenAICompatibleProvider(
            name="openai_compatible",
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            retry_count=config.retry_count,
            call_fn=manager.generate_with_metadata,
        )
    ]

    fallback_model = os.getenv("OPENAI_FALLBACK_MODEL", "").strip()
    if fallback_model and fallback_model != config.model:
        providers.append(
            OpenAICompatibleProvider(
                name="openai_compatible_fallback",
                model=fallback_model,
                timeout_seconds=config.timeout_seconds,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                retry_count=max(0, config.retry_count - 1),
                call_fn=manager.generate_with_metadata,
            )
        )

    router = ProviderFallbackRouter(providers)
    prompt_registry = load_prompt_registry(PROMPTS_ROOT)
    return LLMModelAdapter(
        router=router,
        prompt_registry=prompt_registry,
        default_model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        default_prompt_versions=_prompt_version_overrides(),
    )


def _prompt_version_overrides() -> dict[str, str]:
    mapping = {
        "intake_summary": "LLM_PROMPT_VERSION_INTAKE_SUMMARY",
        "case_summary": "LLM_PROMPT_VERSION_CASE_SUMMARY",
        "wrap_up_summary": "LLM_PROMPT_VERSION_WRAP_UP_SUMMARY",
        "operator_summary": "LLM_PROMPT_VERSION_OPERATOR_SUMMARY",
        "dispatch_summary": "LLM_PROMPT_VERSION_DISPATCH_SUMMARY",
        "intake_user_reply": "LLM_PROMPT_VERSION_INTAKE_USER_REPLY",
        "progress_reply": "LLM_PROMPT_VERSION_PROGRESS_REPLY",
        "handoff_reply": "LLM_PROMPT_VERSION_HANDOFF_REPLY",
        "faq_reply": "LLM_PROMPT_VERSION_FAQ_REPLY",
        "disambiguation_reply": "LLM_PROMPT_VERSION_DISAMBIGUATION_REPLY",
        "switch_reply": "LLM_PROMPT_VERSION_SWITCH_REPLY",
    }
    overrides: dict[str, str] = {}
    for task, env_key in mapping.items():
        value = os.getenv(env_key, "").strip()
        if value:
            overrides[task] = value
    return overrides
