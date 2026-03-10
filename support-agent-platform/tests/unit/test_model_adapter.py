from __future__ import annotations

from core.model_adapter import DeterministicModel, ModelAdapter, PromptRegistry, PromptTemplate


def test_model_adapter_prompt_version_and_fallback() -> None:
    registry = PromptRegistry(
        [
            PromptTemplate(task="intake_summary", version="v1", template="ticket={ticket}"),
            PromptTemplate(task="intake_summary", version="v2", template="ticket-v2={ticket}"),
        ]
    )

    primary = DeterministicModel("primary", fail_when_contains="ticket-v2")
    backup = DeterministicModel("backup")
    adapter = ModelAdapter([primary, backup], registry)

    output = adapter.generate("intake_summary", {"ticket": "T-1"})
    assert output.startswith("[backup]")
    assert "ticket-v2=T-1" in output
