from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Protocol


class ModelProvider(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class PromptTemplate:
    task: str
    version: str
    template: str


class PromptRegistry:
    def __init__(self, templates: list[PromptTemplate] | None = None) -> None:
        self._templates: dict[str, list[PromptTemplate]] = {}
        for tmpl in templates or []:
            self.register(tmpl)

    def register(self, template: PromptTemplate) -> None:
        self._templates.setdefault(template.task, []).append(template)
        self._templates[template.task].sort(key=lambda item: item.version)

    def latest(self, task: str) -> PromptTemplate:
        variants = self._templates.get(task, [])
        if not variants:
            raise KeyError(f"No prompt template registered for task '{task}'")
        return variants[-1]


class DeterministicModel:
    def __init__(self, name: str, *, fail_when_contains: str | None = None) -> None:
        self.name = name
        self._fail_when_contains = fail_when_contains

    def complete(self, prompt: str) -> str:
        if self._fail_when_contains and self._fail_when_contains in prompt:
            raise RuntimeError(f"{self.name} simulated failure")
        return f"[{self.name}] {prompt}"


class ModelAdapter:
    """Prompt-versioned model adapter with ordered fallback providers."""

    def __init__(self, providers: list[ModelProvider], prompt_registry: PromptRegistry) -> None:
        if not providers:
            raise ValueError("At least one model provider is required")
        self._providers = providers
        self._prompt_registry = prompt_registry

    def generate(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
    ) -> str:
        template = self._prompt_registry.latest(task)
        prompt = self._render(template.template, variables)

        ordered = self._ordered_providers(preferred_provider)
        errors: list[str] = []
        for provider in ordered:
            try:
                return provider.complete(prompt)
            except Exception as exc:  # pragma: no cover - defensive for provider runtime errors
                errors.append(f"{provider.name}: {exc}")

        joined = "; ".join(errors)
        raise RuntimeError(f"All providers failed for task '{task}'. Details: {joined}")

    def _ordered_providers(self, preferred_provider: str | None) -> list[ModelProvider]:
        if preferred_provider is None:
            return list(self._providers)

        preferred = [
            provider for provider in self._providers if provider.name == preferred_provider
        ]
        rest = [provider for provider in self._providers if provider.name != preferred_provider]
        return preferred + rest

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
