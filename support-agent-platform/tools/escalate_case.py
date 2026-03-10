from __future__ import annotations

from typing import cast

from core.ticket_api import TicketAPI
from storage.models import TicketPriority


def escalate_case(
    ticket_api: TicketAPI,
    *,
    ticket_id: str,
    actor_id: str,
    reason: str,
    new_priority: str = "P1",
) -> dict[str, str]:
    if new_priority not in {"P1", "P2", "P3", "P4"}:
        raise ValueError(f"Invalid priority: {new_priority}")
    ticket = ticket_api.escalate_ticket(
        ticket_id,
        actor_id=actor_id,
        reason=reason,
        new_priority=cast(TicketPriority, new_priority),
    )
    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
        "priority": ticket.priority,
    }
