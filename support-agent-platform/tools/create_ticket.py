from __future__ import annotations

from typing import Any, cast

from core.ticket_api import TicketAPI
from storage.models import TicketPriority


def create_ticket(ticket_api: TicketAPI, payload: dict[str, Any]) -> dict[str, Any]:
    priority = _normalize_priority(payload.get("priority", "P3"))
    ticket = ticket_api.create_ticket(
        channel=str(payload["channel"]),
        session_id=str(payload["session_id"]),
        thread_id=str(payload["thread_id"]),
        title=str(payload["title"]),
        latest_message=str(payload["latest_message"]),
        intent=str(payload["intent"]),
        priority=priority,
        queue=str(payload.get("queue", "support")),
        customer_id=str(payload.get("customer_id")) if payload.get("customer_id") else None,
        assignee=str(payload.get("assignee")) if payload.get("assignee") else None,
        metadata=dict(payload.get("metadata") or {}),
    )
    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
        "priority": ticket.priority,
    }


def _normalize_priority(value: Any) -> TicketPriority:
    text = str(value)
    if text not in {"P1", "P2", "P3", "P4"}:
        raise ValueError(f"Invalid priority: {text}")
    return cast(TicketPriority, text)
