from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class PromptDefinition:
    prompt_key: str
    prompt_version: str
    scenario: str
    expected_schema: str
    template: str
    source_path: Path


class PromptRegistry:
    def __init__(self, prompts: list[PromptDefinition] | None = None) -> None:
        self._prompts: dict[str, list[PromptDefinition]] = {}
        for prompt in prompts or []:
            self.register(prompt)

    def register(self, prompt: PromptDefinition) -> None:
        versions = self._prompts.setdefault(prompt.prompt_key, [])
        versions.append(prompt)
        versions.sort(key=lambda item: _version_sort_key(item.prompt_version))

    def resolve(self, prompt_key: str, version: str | None = None) -> PromptDefinition:
        variants = self._prompts.get(prompt_key, [])
        if not variants:
            raise KeyError(f"Prompt not found: {prompt_key}")
        if version is None:
            return variants[-1]
        for item in variants:
            if item.prompt_version == version:
                return item
        raise KeyError(f"Prompt version not found: {prompt_key}@{version}")

    def available_versions(self, prompt_key: str) -> list[str]:
        return [item.prompt_version for item in self._prompts.get(prompt_key, [])]


def load_prompt_registry(prompts_root: Path) -> PromptRegistry:
    prompts: list[PromptDefinition] = []
    for path in sorted(prompts_root.glob("*/*.md")):
        prompts.append(_parse_prompt_file(path))
    return PromptRegistry(prompts)


def _parse_prompt_file(path: Path) -> PromptDefinition:
    content = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    body = content
    if content.startswith("---\n"):
        parts = content.split("\n---\n", 1)
        if len(parts) == 2:
            metadata = _parse_front_matter(parts[0][4:])
            body = parts[1]

    stem_parts = path.stem.split(".")
    inferred_key = stem_parts[0]
    inferred_version = stem_parts[1] if len(stem_parts) > 1 else "v1"
    prompt_key = metadata.get("prompt_key", inferred_key)
    prompt_version = metadata.get("prompt_version", inferred_version)
    scenario = metadata.get("scenario", path.parent.name)
    expected_schema = metadata.get("expected_schema", "text/plain")
    template = body.strip()
    if not template:
        raise ValueError(f"Prompt template is empty: {path}")
    return PromptDefinition(
        prompt_key=prompt_key,
        prompt_version=prompt_version,
        scenario=scenario,
        expected_schema=expected_schema,
        template=template,
        source_path=path,
    )


def _parse_front_matter(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def _version_sort_key(version: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", version)
    if match:
        return int(match.group(1)), version
    return 0, version
