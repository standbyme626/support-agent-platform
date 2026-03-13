from __future__ import annotations

from pathlib import Path
from string import Formatter

import pytest

from llm.tracing.prompt_registry import PromptRegistry, load_prompt_registry


def _write_prompt(path: Path, *, key: str, version: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f"prompt_key: {key}",
                f"prompt_version: {version}",
                f"scenario: {path.parent.name}",
                "expected_schema: text/plain",
                "---",
                body,
            ]
        ),
        encoding="utf-8",
    )


def test_prompt_registry_loads_and_resolves_latest_version(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path / "intake" / "intake_summary.v1.md",
        key="intake_summary",
        version="v1",
        body="v1 template {ticket}",
    )
    _write_prompt(
        tmp_path / "intake" / "intake_summary.v2.md",
        key="intake_summary",
        version="v2",
        body="v2 template {ticket}",
    )

    registry = load_prompt_registry(tmp_path)
    latest = registry.resolve("intake_summary")
    assert latest.prompt_version == "v2"
    assert "v2 template" in latest.template

    v1 = registry.resolve("intake_summary", version="v1")
    assert v1.prompt_version == "v1"
    assert "v1 template" in v1.template


def test_prompt_registry_raises_on_unknown_prompt() -> None:
    registry = PromptRegistry()
    with pytest.raises(KeyError) as exc:
        registry.resolve("missing_prompt")
    assert "missing_prompt" in str(exc.value)


def test_intake_prompts_do_not_treat_json_keys_as_template_variables() -> None:
    prompts_root = Path(__file__).resolve().parents[2] / "llm" / "prompts" / "intake"
    invalid_fields: list[tuple[str, str]] = []
    for path in sorted(prompts_root.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        body = content.split("\n---\n", 1)[1] if content.startswith("---\n") else content
        fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(body)
            if field_name is not None
        }
        for field in fields:
            if '"' in field or "'" in field:
                invalid_fields.append((path.name, field))
    assert invalid_fields == []
