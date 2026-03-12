from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, ClassVar

from openclaw_adapter.session_mapper import SessionMapper
from storage.models import LifecycleStage, Ticket, TicketEvent, TicketPriority, TicketStatus
from storage.ticket_repository import TicketRepository


class TicketAPI:
    """Ticket-centric domain API used by tools and workflows.

    Lifecycle transitions and guardrails are owned here instead of OpenClaw adapters.
    """

    _ALLOWED_STATUS_TRANSITIONS: ClassVar[dict[TicketStatus, set[TicketStatus]]] = {
        "open": {"pending", "escalated", "handoff", "resolved", "closed"},
        "pending": {"open", "escalated", "handoff", "resolved", "closed"},
        "escalated": {"pending", "handoff", "resolved", "closed"},
        "handoff": {"pending", "escalated", "resolved", "closed"},
        "resolved": {"open", "pending", "closed"},
        "closed": set(),
    }

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
        risk_level: str = "medium",
        inbox: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Ticket:
        normalized_inbox = inbox or str((metadata or {}).get("inbox") or channel)
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
            inbox=normalized_inbox,
            source_channel=channel,
            risk_level=risk_level,
            metadata=metadata,
        )
        self._repository.append_event(
            ticket_id=ticket.ticket_id,
            event_type="ticket_created",
            actor_type="system",
            actor_id="ticket-api",
            payload={
                "snapshot": asdict(ticket),
                "policy": "ticket_lifecycle_v1",
                "inbox": normalized_inbox,
            },
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

        if "status" in merged_updates:
            requested_status = merged_updates.pop("status")
            if requested_status != current.status:
                updated = self._transition_status(
                    ticket_id=ticket_id,
                    new_status=requested_status,
                    actor_id=actor_id,
                    event_type="ticket_status_changed",
                    extra_updates=merged_updates,
                    payload={"requested_via": "update_ticket"},
                )
                return updated

        updated = self._repository.update_ticket(ticket_id, merged_updates)
        self._repository.append_event(
            ticket_id=ticket_id,
            event_type="ticket_updated",
            actor_type="agent",
            actor_id=actor_id,
            payload={"updates": merged_updates},
        )
        return updated

    def assign_ticket(self, ticket_id: str, assignee: str, *, actor_id: str) -> Ticket:
        current = self.require_ticket(ticket_id)
        self._ensure_not_closed(current)
        event_type = "ticket_reassigned" if current.assignee else "ticket_assigned"

        updated = self._transition_status(
            ticket_id=ticket_id,
            new_status="pending",
            actor_id=actor_id,
            event_type=event_type,
            extra_updates={
                "assignee": assignee,
                "lifecycle_stage": "classified",
                "last_agent_action": f"assign:{assignee}",
            },
            payload={"assignee": assignee},
        )
        return updated

    def close_ticket(
        self,
        ticket_id: str,
        *,
        actor_id: str,
        resolution_note: str,
        close_reason: str | None = None,
        resolution_code: str | None = None,
        handoff_state: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Ticket:
        current = self.require_ticket(ticket_id)
        self._ensure_not_closed(current)

        if current.status != "resolved":
            self.resolve_ticket(
                ticket_id=ticket_id,
                actor_id=actor_id,
                resolution_note=resolution_note,
                resolution_code=resolution_code,
            )

        updates: dict[str, Any] = {
            "needs_handoff": False,
            "latest_message": resolution_note,
            "resolution_note": resolution_note,
            "resolution_code": resolution_code,
            "close_reason": close_reason or "agent_close",
            "closed_at": datetime.now(UTC),
            "lifecycle_stage": "closed",
            "last_agent_action": "close",
        }
        if handoff_state is not None:
            updates["handoff_state"] = handoff_state
        if metadata is not None:
            updates["metadata"] = metadata

        return self._transition_status(
            ticket_id=ticket_id,
            new_status="closed",
            actor_id=actor_id,
            event_type="ticket_closed",
            extra_updates=updates,
            payload={
                "resolution_note": resolution_note,
                "resolution_code": resolution_code,
                "close_reason": close_reason or "agent_close",
            },
        )

    def resolve_ticket(
        self,
        ticket_id: str,
        *,
        actor_id: str,
        resolution_note: str,
        resolution_code: str | None = None,
    ) -> Ticket:
        current = self.require_ticket(ticket_id)
        self._ensure_not_closed(current)
        return self._transition_status(
            ticket_id=ticket_id,
            new_status="resolved",
            actor_id=actor_id,
            event_type="ticket_resolved",
            extra_updates={
                "needs_handoff": False,
                "latest_message": resolution_note,
                "resolution_note": resolution_note,
                "resolution_code": resolution_code,
                "resolved_at": datetime.now(UTC),
                "lifecycle_stage": "resolved",
                "last_agent_action": "resolve",
            },
            payload={"resolution_note": resolution_note, "resolution_code": resolution_code},
        )

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

        return self._transition_status(
            ticket_id=ticket_id,
            new_status="escalated",
            actor_id=actor_id,
            event_type="ticket_escalated",
            extra_updates={
                "priority": new_priority,
                "escalated_at": datetime.now(UTC),
                "lifecycle_stage": "awaiting_human",
                "handoff_state": "requested",
                "risk_level": "high",
                "last_agent_action": "escalate",
            },
            payload={"reason": reason, "priority": new_priority},
        )

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

    def merge_ticket_metadata(
        self,
        ticket_id: str,
        metadata_patch: dict[str, Any],
        *,
        actor_id: str,
    ) -> Ticket:
        return self.update_ticket(
            ticket_id,
            {"metadata": metadata_patch},
            actor_id=actor_id,
        )

    def list_all_tickets(self, *, limit: int = 5000) -> list[Ticket]:
        return self._repository.list_tickets(limit=limit, offset=0)

    def pending_actions(self, ticket_id: str) -> list[dict[str, Any]]:
        ticket = self.require_ticket(ticket_id)
        raw = ticket.metadata.get("pending_actions")
        if not isinstance(raw, list):
            return []
        return [dict(item) for item in raw if isinstance(item, dict)]

    @staticmethod
    def _ensure_not_closed(ticket: Ticket) -> None:
        if ticket.status == "closed":
            raise RuntimeError(f"Ticket {ticket.ticket_id} is already closed")

    def _transition_status(
        self,
        *,
        ticket_id: str,
        new_status: str,
        actor_id: str,
        event_type: str,
        extra_updates: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Ticket:
        current = self.require_ticket(ticket_id)
        status = self._normalize_status(new_status)

        if status != current.status:
            self._assert_transition_allowed(current.status, status, ticket_id=ticket_id)

        updates = dict(extra_updates or {})
        updates["status"] = status
        updates.setdefault(
            "lifecycle_stage",
            self._stage_for_status(status, current.lifecycle_stage),
        )
        updated = self._repository.update_ticket(ticket_id, updates)
        self._repository.append_event(
            ticket_id=ticket_id,
            event_type=event_type,
            actor_type="agent",
            actor_id=actor_id,
            payload={
                "from_status": current.status,
                "to_status": status,
                "policy": "ticket_lifecycle_v1",
                **(payload or {}),
            },
        )
        return updated

    @classmethod
    def _normalize_status(cls, value: str) -> TicketStatus:
        normalized = value.strip().lower()
        if normalized not in cls._ALLOWED_STATUS_TRANSITIONS:
            raise ValueError(f"Unsupported status: {value}")
        return normalized  # type: ignore[return-value]

    @classmethod
    def _assert_transition_allowed(
        cls, current: TicketStatus, target: TicketStatus, *, ticket_id: str
    ) -> None:
        if target == current:
            return
        allowed = cls._ALLOWED_STATUS_TRANSITIONS[current]
        if target not in allowed:
            raise RuntimeError(
                f"Invalid lifecycle transition for {ticket_id}: {current} -> {target}"
            )

    @staticmethod
    def _stage_for_status(status: TicketStatus, fallback: LifecycleStage) -> LifecycleStage:
        mapping: dict[TicketStatus, LifecycleStage] = {
            "open": fallback,
            "pending": "classified",
            "escalated": "awaiting_human",
            "handoff": "awaiting_human",
            "resolved": "resolved",
            "closed": "closed",
        }
        return mapping[status]
