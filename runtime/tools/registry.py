from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    description: str
    owner: str


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(self, tool: ToolRegistration) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolRegistration:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"tool {name!r} is not registered") from exc

    def list_names(self) -> list[str]:
        return sorted(self._tools)

    def list_all(self) -> list[ToolRegistration]:
        return [self._tools[name] for name in self.list_names()]


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (
        ToolRegistration(
            name="retriever.search_kb",
            description="Retrieve grounding documents from KB and SOP corpus.",
            owner="core.retriever.Retriever",
        ),
        ToolRegistration(
            name="summary.generate_ticket_summary",
            description="Build concise issue timeline and summary cards.",
            owner="core.summary_engine.SummaryEngine",
        ),
        ToolRegistration(
            name="ticket.apply_transition",
            description="Apply controlled ticket status transitions with audit events.",
            owner="core.ticket_api.TicketAPI",
        ),
        ToolRegistration(
            name="ops.recommended_actions",
            description="Propose operator actions with confidence and evidence.",
            owner="core.recommended_actions_engine.RecommendedActionsEngine",
        ),
    ):
        registry.register(tool)
    return registry
