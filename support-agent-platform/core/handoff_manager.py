from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from storage.models import Ticket, TicketEvent

from .intent_router import IntentDecision
from .recommended_actions_engine import RecommendedAction
from .ticket_api import TicketAPI


@dataclass(frozen=True)
class HandoffDecision:
    should_handoff: bool
    reason: str
    payload: Mapping[str, object]


class HandoffManager:
    """Human handoff policies for complex/high-risk cases."""

    def evaluate(
        self,
        *,
        ticket: Ticket,
        intent: IntentDecision,
        case_summary: str,
        recommendations: list[RecommendedAction],
        recent_events: list[TicketEvent],
    ) -> HandoffDecision:
        reasons: list[str] = []

        if ticket.priority == "P1":
            reasons.append("priority-P1")
        if ticket.intent == "complaint":
            reasons.append("complaint-intent")
        if intent.is_low_confidence:
            reasons.append("low-confidence")
        if "人工" in ticket.latest_message or (
            "人" in ticket.latest_message and "客服" in ticket.latest_message
        ):
            reasons.append("customer-asks-human")

        should_handoff = len(reasons) > 0
        payload = {
            "ticket_id": ticket.ticket_id,
            "summary": case_summary,
            "evidence_events": [event.event_type for event in recent_events[-5:]],
            "recommended_actions": [action.action for action in recommendations],
        }

        if not should_handoff:
            return HandoffDecision(False, "no-trigger", payload)

        return HandoffDecision(True, ";".join(reasons), payload)

    def mark_handoff(
        self, ticket_api: TicketAPI, ticket_id: str, decision: HandoffDecision
    ) -> Ticket:
        ticket = ticket_api.update_ticket(
            ticket_id,
            {
                "status": "handoff",
                "needs_handoff": True,
                "queue": "human-handoff",
            },
            actor_id="handoff-manager",
        )
        ticket_api.add_event(
            ticket_id,
            event_type="handoff_triggered",
            actor_type="system",
            actor_id="handoff-manager",
            payload={"reason": decision.reason, "payload": decision.payload},
        )
        return ticket

    def resume(self, ticket_api: TicketAPI, ticket_id: str, *, actor_id: str, note: str) -> Ticket:
        ticket = ticket_api.update_ticket(
            ticket_id,
            {
                "status": "pending",
                "needs_handoff": False,
                "latest_message": note,
            },
            actor_id=actor_id,
        )
        ticket_api.add_event(
            ticket_id,
            event_type="handoff_resumed",
            actor_type="agent",
            actor_id=actor_id,
            payload={"note": note},
        )
        return ticket
