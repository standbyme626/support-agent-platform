from __future__ import annotations

from core.ticket_api import TicketAPI


def assign_ticket(
    ticket_api: TicketAPI,
    *,
    ticket_id: str,
    assignee: str,
    actor_id: str,
) -> dict[str, str | None]:
    ticket = ticket_api.assign_ticket(ticket_id, assignee=assignee, actor_id=actor_id)
    return {
        "ticket_id": ticket.ticket_id,
        "assignee": ticket.assignee,
        "status": ticket.status,
    }
