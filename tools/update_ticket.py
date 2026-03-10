from __future__ import annotations

from typing import Any

from core.ticket_api import TicketAPI


def update_ticket(
    ticket_api: TicketAPI,
    *,
    ticket_id: str,
    updates: dict[str, Any],
    actor_id: str,
) -> dict[str, Any]:
    ticket = ticket_api.update_ticket(ticket_id, updates, actor_id=actor_id)
    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }
