from __future__ import annotations

from core.ticket_api import TicketAPI


def close_case(
    ticket_api: TicketAPI,
    *,
    ticket_id: str,
    actor_id: str,
    resolution_note: str,
) -> dict[str, str]:
    ticket = ticket_api.close_ticket(ticket_id, actor_id=actor_id, resolution_note=resolution_note)
    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
    }
