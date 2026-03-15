from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuntimeMode = Literal["langgraph-node", "deep-agent", "graph-gated"]


@dataclass(frozen=True)
class AgentRegistration:
    name: str
    role: str
    runtime_mode: RuntimeMode
    toolset: tuple[str, ...]
    description: str


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentRegistration] = {}

    def register(self, agent: AgentRegistration) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> AgentRegistration:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"agent {name!r} is not registered") from exc

    def list_names(self) -> list[str]:
        return sorted(self._agents)

    def list_all(self) -> list[AgentRegistration]:
        return [self._agents[name] for name in self.list_names()]


def build_default_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()
    for agent in (
        AgentRegistration(
            name="intake-agent",
            role="entry intent and grounding",
            runtime_mode="langgraph-node",
            toolset=("retriever.search_kb", "summary.generate_ticket_summary"),
            description="Lightweight intake node that routes FAQ/ticket-open behavior.",
        ),
        AgentRegistration(
            name="case-copilot-agent",
            role="ticket-scoped investigation",
            runtime_mode="deep-agent",
            toolset=("retriever.search_kb", "summary.generate_ticket_summary"),
            description="Multi-step case investigation harness with traceable outputs.",
        ),
        AgentRegistration(
            name="operator-supervisor-agent",
            role="queue/SLA risk advisor",
            runtime_mode="deep-agent",
            toolset=("ops.recommended_actions", "retriever.search_kb"),
            description="Operator copilot for queue pressure and SLA risk analysis.",
        ),
        AgentRegistration(
            name="dispatch-collaboration-agent",
            role="dispatch suggestion under policy gate",
            runtime_mode="graph-gated",
            toolset=("ops.recommended_actions", "ticket.apply_transition"),
            description="Dispatch advisor that proposes routing but does not auto-execute.",
        ),
    ):
        registry.register(agent)
    return registry
