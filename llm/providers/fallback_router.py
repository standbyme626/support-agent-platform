from __future__ import annotations

from dataclasses import replace

from .base import LLMProvider, ProviderCallContext, ProviderCallResult


class ProviderExhaustedError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("All providers failed: " + "; ".join(errors))


class ProviderFallbackRouter:
    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required")
        self._providers = providers

    def complete(
        self,
        prompt: str,
        *,
        context: ProviderCallContext,
        preferred_provider: str | None = None,
    ) -> ProviderCallResult:
        ordered = self._ordered_providers(preferred_provider)
        errors: list[str] = []
        for index, provider in enumerate(ordered):
            try:
                result = provider.complete(prompt, context=context)
                if index > 0 or errors:
                    return replace(result, fallback_used=True)
                return result
            except Exception as exc:  # pragma: no cover - defensive provider runtime handling
                errors.append(f"{provider.name}: {exc}")

        raise ProviderExhaustedError(errors)

    def _ordered_providers(self, preferred_provider: str | None) -> list[LLMProvider]:
        if not preferred_provider:
            return list(self._providers)

        preferred = [provider for provider in self._providers if provider.name == preferred_provider]
        remaining = [provider for provider in self._providers if provider.name != preferred_provider]
        return preferred + remaining
