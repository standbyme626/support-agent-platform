from __future__ import annotations

from dataclasses import asdict
from typing import Any

from openclaw_adapter.session_mapper import SessionMapper
from storage.models import Ticket, TicketEvent, TicketPriority
from storage.ticket_repository import TicketRepository


class TicketAPI:
    """Ticket-centric domain API used by tools and workflows."""

    def __init__(
        self, repository: TicketRepository, session_mapper: SessionMapper | None = None
    ) -> None:
        self._repository = repository
        self._session_mapper = session_mapper

    def create_ticket(
        self,
        *,
        channel: str,
        session_id: str,
        thread_id: str,
        title: str,
        latest_message: str,
        intent: str,
        priority: TicketPriority = "P3",
        queue: str = "support",
        customer_id: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Ticket:
        ticket = self._repository.create_ticket(
            channel=channel,
            session_id=session_id,
            thread_id=thread_id,
            customer_id=customer_id,
            title=title,
            latest_message=latest_message,
            intent=intent,
            priority=priority,
            queue=queue,
            assignee=assignee,
            metadata=metadata,
        )
        self._repository.append_event(
            ticket_id=ticket.ticket_id,
            event_type="created",
            actor_type="system",
            actor_id="ticket-api",
            payload={"snapshot": asdict(ticket)},
        )
        if self._session_mapper is not None:
            self._session_mapper.set_ticket_id(session_id, ticket.ticket_id, metadata=metadata)
        return ticket

    def update_ticket(self, ticket_id: str, updates: dict[str, Any], *, actor_id: str) -> Ticket:
        current = self.require_ticket(ticket_id)
        self._ensure_not_closed(current)

        merged_updates = dict(updates)
        if "metadata" in merged_updates:
            metadata = dict(current.metadata)
            metadata.update(dict(merged_updates["metadata"]))
            merged_updates["metadata"] = metadata

        updated = self._repository.update_ticket(ticket_id, merged_updates)
        self._repository.append_event(
            ticket_id=ticket_id,
            event_type="updated",
            actor_type="agent",
            actor_id=actor_id,
            payload={"updates": merged_updates},
        )
        return updated

    def assign_ticket(self, ticket_id: str, assignee: str, *, actor_id: str) -> Ticket:
        current = self.require_ticket(ticket_id)
        self._ensure_not_closed(current)
        event_type = "reassigned" if current.assignee else "assigned"

        updated = self._repository.update_ticket(
            ticket_id,
            {
                "assignee": assignee,
                "status": "pending",
            },
        )
        self._repository.append_event(
            ticket_id=ticket_id,
            event_type=event_type,
            actor_type="agent",
            actor_id=actor_id,
            payload={"assignee": assignee},
        )
        return updated

    def close_ticket(self, ticket_id: str, *, actor_id: str, resolution_note: str) -> Ticket:
        current = self.require_ticket(ticket_id)
        self._ensure_not_closed(current)

        updated = self._repository.update_ticket(
            ticket_id,
            {
                "status": "closed",
                "needs_handoff": False,
                "latest_message": resolution_note,
            },
        )
        self._repository.append_event(
            ticket_id=ticket_id,
            event_type="closed",
            actor_type="agent",
            actor_id=actor_id,
            payload={"resolution_note": resolution_note},
        )
        return updated

    def escalate_ticket(
        self,
        ticket_id: str,
        *,
        actor_id: str,
        reason: str,
        new_priority: TicketPriority = "P1",
    ) -> Ticket:
        current = self.require_ticket(ticket_id)
        self._ensure_not_closed(current)

        updated = self._repository.update_ticket(
            ticket_id,
            {
                "status": "escalated",
                "priority": new_priority,
            },
        )
        self._repository.append_event(
            ticket_id=ticket_id,
            event_type="escalated",
            actor_type="agent",
            actor_id=actor_id,
            payload={"reason": reason, "priority": new_priority},
        )
        return updated

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self._repository.get_ticket(ticket_id)

    def require_ticket(self, ticket_id: str) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            raise KeyError(f"Ticket not found: {ticket_id}")
        return ticket

    def list_tickets(
        self,
        *,
        status: str | None = None,
        queue: str | None = None,
        assignee: str | None = None,
        limit: int = 100,
    ) -> list[Ticket]:
        return self._repository.list_tickets(
            status=status,
            queue=queue,
            assignee=assignee,
            limit=limit,
        )

    def list_events(self, ticket_id: str) -> list[TicketEvent]:
        return self._repository.list_events(ticket_id)

    def add_event(
        self,
        ticket_id: str,
        *,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any] | None = None,
    ) -> TicketEvent:
        return self._repository.append_event(
            ticket_id=ticket_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )

    @staticmethod
    def _ensure_not_closed(ticket: Ticket) -> None:
        if ticket.status == "closed":
            raise RuntimeError(f"Ticket {ticket.ticket_id} is already closed")
