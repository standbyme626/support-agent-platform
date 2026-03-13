from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from storage.models import KBDocument, Ticket, TicketEvent

from .handoff_manager import HandoffDecision
from .intent_router import IntentDecision
from .recommended_actions_engine import RecommendedAction

ReplyGenerationType = Literal[
    "faq",
    "progress",
    "handoff",
    "generic",
    "disambiguation",
    "switch",
]


@dataclass(frozen=True)
class ReplyContext:
    message_text: str
    intent: IntentDecision
    ticket: Ticket
    summary: str
    retrieved_docs: list[KBDocument]
    recommendations: list[RecommendedAction]
    handoff: HandoffDecision
    events: list[TicketEvent]
    tone: str
    session_mode: str | None
    disambiguation_decision: str | None
    disambiguation_reason: str | None


def resolve_generation_type(
    *,
    intent: IntentDecision,
    handoff: HandoffDecision,
    forced_generation_type: ReplyGenerationType | None,
    disambiguation_decision: str | None,
    disambiguation_reason: str | None,
) -> ReplyGenerationType:
    if forced_generation_type is not None:
        return forced_generation_type
    if disambiguation_decision == "awaiting_disambiguation":
        return "disambiguation"
    if disambiguation_reason in {"explicit_ticket_in_message", "requested_ticket_id"}:
        return "switch"
    if handoff.should_handoff:
        return "handoff"
    if intent.intent == "faq":
        return "faq"
    if intent.intent == "progress_query":
        return "progress"
    return "generic"


def build_reply_variables(context: ReplyContext) -> dict[str, str]:
    grounding = [
        {
            "doc_id": doc.doc_id,
            "source_type": doc.source_type,
            "title": doc.title,
            "score": doc.score,
        }
        for doc in context.retrieved_docs[:3]
    ]
    recommendation_payload = [
        {
            "action": item.action,
            "reason": item.reason,
            "source": item.source,
            "risk": item.risk,
            "confidence": item.confidence,
            "evidence": [
                {"doc_id": evidence.doc_id, "source_type": evidence.source_type}
                for evidence in item.evidence
            ],
        }
        for item in context.recommendations[:3]
    ]
    latest_events = [
        {
            "event_type": event.event_type,
            "actor": event.actor_id,
        }
        for event in context.events[-5:]
    ]
    return {
        "user_message": context.message_text,
        "intent": context.intent.intent,
        "intent_confidence": f"{context.intent.confidence:.2f}",
        "ticket_id": context.ticket.ticket_id,
        "ticket_status": context.ticket.status,
        "ticket_priority": context.ticket.priority,
        "ticket_queue": context.ticket.queue,
        "ticket_assignee": context.ticket.assignee or "unassigned",
        "handoff_decision": "true" if context.handoff.should_handoff else "false",
        "handoff_reason": context.handoff.reason,
        "summary": context.summary,
        "grounding_sources": json.dumps(grounding, ensure_ascii=False),
        "recommendations": json.dumps(recommendation_payload, ensure_ascii=False),
        "latest_events": json.dumps(latest_events, ensure_ascii=False),
        "tone": context.tone,
        "session_mode": context.session_mode or "",
        "disambiguation_decision": context.disambiguation_decision or "",
        "disambiguation_reason": context.disambiguation_reason or "",
    }
