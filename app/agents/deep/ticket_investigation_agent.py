from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable


@dataclass(frozen=True)
class InvestigationContext:
    ticket_id: str
    question: str
    actor_id: str
    metadata: dict[str, Any]


class TicketInvestigationAgent:
    """Analysis-only deep agent that never executes high-risk ticket actions."""

    def __init__(
        self,
        *,
        read_ticket_tool: Callable[..., Any] | None = None,
        read_ticket_events_tool: Callable[..., Any] | None = None,
        search_kb_tool: Callable[..., Any] | None = None,
        search_similar_cases_tool: Callable[..., Any] | None = None,
        get_grounding_sources_tool: Callable[..., Any] | None = None,
        draft_reply_tool: Callable[..., Any] | None = None,
        propose_actions_tool: Callable[..., Any] | None = None,
    ) -> None:
        self._read_ticket_tool = read_ticket_tool
        self._read_ticket_events_tool = read_ticket_events_tool
        self._search_kb_tool = search_kb_tool
        self._search_similar_cases_tool = search_similar_cases_tool
        self._get_grounding_sources_tool = get_grounding_sources_tool
        self._draft_reply_tool = draft_reply_tool
        self._propose_actions_tool = propose_actions_tool

    def analyze(
        self,
        ticket_id: str,
        *,
        question: str | None = None,
        actor_id: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = InvestigationContext(
            ticket_id=ticket_id,
            question=question or "Please investigate this ticket and provide recommendations.",
            actor_id=actor_id,
            metadata=metadata or {},
        )

        ticket_snapshot = _safe_tool_call(self._read_ticket_tool, ticket_id=ticket_id)
        ticket_events = _safe_tool_call(self._read_ticket_events_tool, ticket_id=ticket_id)
        kb_hits = _safe_tool_call(self._search_kb_tool, query=context.question)
        similar_cases = _safe_tool_call(self._search_similar_cases_tool, ticket_id=ticket_id)
        grounding = _safe_tool_call(self._get_grounding_sources_tool, ticket_id=ticket_id)

        suggested_actions = _safe_tool_call(
            self._propose_actions_tool,
            ticket_id=ticket_id,
            question=context.question,
        )
        if suggested_actions is None:
            suggested_actions = [
                "Confirm impact scope with customer.",
                "Ask on-call operator to validate latest remediation status.",
                "Escalate manually via HITL if risk increases.",
            ]

        reply_draft = _safe_tool_call(
            self._draft_reply_tool,
            ticket_id=ticket_id,
            summary="Investigation completed with evidence-backed recommendations.",
            question=context.question,
        )
        if reply_draft is None:
            reply_draft = (
                "We have reviewed your case and collected relevant evidence. "
                "Next, we recommend validating the latest recovery status and sharing an update shortly."
            )

        evidence = [
            {"source": "ticket", "data": ticket_snapshot},
            {"source": "events", "data": ticket_events},
            {"source": "kb", "data": kb_hits},
            {"source": "similar_cases", "data": similar_cases},
            {"source": "grounding", "data": grounding},
        ]

        return {
            "ticket_id": context.ticket_id,
            "actor_id": context.actor_id,
            "question": context.question,
            "summary": "Analysis generated. No terminal action was executed by the agent.",
            "evidence": evidence,
            "recommended_actions": suggested_actions,
            "reply_draft": reply_draft,
            "safety": {
                "advice_only": True,
                "high_risk_actions_executed": [],
                "requires_hitl_for_terminal_actions": True,
            },
            "trace": {
                "agent": "ticket_investigation_agent_v1",
                "generated_at": datetime.now(UTC).isoformat(),
            },
        }


def build_ticket_investigation_agent(
    *,
    model: str | None = None,
    memory_store: Any = None,
    read_ticket_tool: Callable[..., Any] | None = None,
    read_ticket_events_tool: Callable[..., Any] | None = None,
    search_kb_tool: Callable[..., Any] | None = None,
    search_similar_cases_tool: Callable[..., Any] | None = None,
    get_grounding_sources_tool: Callable[..., Any] | None = None,
    draft_reply_tool: Callable[..., Any] | None = None,
    propose_actions_tool: Callable[..., Any] | None = None,
) -> TicketInvestigationAgent:
    _ = model
    _ = memory_store
    return TicketInvestigationAgent(
        read_ticket_tool=read_ticket_tool,
        read_ticket_events_tool=read_ticket_events_tool,
        search_kb_tool=search_kb_tool,
        search_similar_cases_tool=search_similar_cases_tool,
        get_grounding_sources_tool=get_grounding_sources_tool,
        draft_reply_tool=draft_reply_tool,
        propose_actions_tool=propose_actions_tool,
    )


def run_ticket_investigation(
    agent: TicketInvestigationAgent,
    *,
    ticket_id: str,
    actor: str,
    question: str,
) -> dict[str, Any]:
    return agent.analyze(ticket_id, question=question, actor_id=actor)


def _safe_tool_call(tool: Callable[..., Any] | None, **kwargs: Any) -> Any:
    if tool is None:
        return None
    try:
        return tool(**kwargs)
    except TypeError:
        if "ticket_id" in kwargs and len(kwargs) == 1:
            try:
                return tool(kwargs["ticket_id"])
            except Exception:
                return None
    except Exception:
        return None
    return None
