from __future__ import annotations

from typing import Any

from app.domain.systems.base import BaseSystem, SystemAction


TICKET_LIFECYCLE = (
    "new",
    "triaged",
    "assigned",
    "in_progress",
    "escalated",
    "resolved",
    "closed",
)

TICKET_ACTIONS = {
    "assign": SystemAction(
        name="assign",
        allowed_from=frozenset({"triaged"}),
        to_status="assigned",
        required_fields=("assignee_id",),
    ),
    "escalate": SystemAction(
        name="escalate",
        allowed_from=frozenset({"assigned", "in_progress"}),
        to_status="escalated",
        required_fields=("escalation_level",),
    ),
    "resolve": SystemAction(
        name="resolve",
        allowed_from=frozenset({"in_progress", "escalated", "assigned"}),
        to_status="resolved",
        required_fields=(),
    ),
    "close": SystemAction(
        name="close",
        allowed_from=frozenset({"resolved"}),
        to_status="closed",
        required_fields=("close_reason",),
    ),
    "reopen": SystemAction(
        name="reopen",
        allowed_from=frozenset({"resolved", "closed"}),
        to_status="new",
        required_fields=(),
    ),
}


def create_ticket_system(ticket_repository: Any) -> BaseSystem:
    from datetime import UTC, datetime

    class TicketSystem(BaseSystem):
        @property
        def system_key(self) -> str:
            return "ticket"

        @property
        def entity_type(self) -> str:
            return "ticket"

        @property
        def id_prefix(self) -> str:
            return "T-"

        @property
        def lifecycle(self) -> tuple[str, ...]:
            return TICKET_LIFECYCLE

        @property
        def terminal_status(self) -> str:
            return "closed"

        @property
        def actions(self) -> dict[str, SystemAction]:
            return TICKET_ACTIONS

        def create(self, payload: dict[str, Any]) -> dict[str, Any]:
            now = datetime.now(UTC).isoformat()
            ticket = self._repo.create_ticket(
                channel=payload.get("channel", "api"),
                session_id=payload.get("session_id", ""),
                thread_id=payload.get("thread_id", ""),
                title=payload.get("title", ""),
                latest_message=payload.get("description", payload.get("latest_message", "")),
                intent=payload.get("intent", "general"),
                priority=payload.get("priority", "medium"),
                queue=payload.get("queue", "default"),
                customer_id=payload.get("customer_id"),
                assignee=payload.get("assignee"),
                metadata=payload.get("metadata"),
            )
            return {
                "ok": True,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": ticket.ticket_id,
                "status": ticket.status,
                "created_at": now,
                "updated_at": now,
                "data": self._ticket_to_dict(ticket),
            }

        def get(self, entity_id: str) -> dict[str, Any] | None:
            ticket = self._repo.get_ticket(entity_id)
            if ticket is None:
                return None
            return self._ticket_to_dict(ticket)

        def list(
            self,
            filters: dict[str, Any] | None = None,
            page: int = 1,
            page_size: int = 20,
        ) -> dict[str, Any]:
            filters = filters or {}
            tickets = self._repo.list_tickets(
                status=filters.get("status"),
                priority=filters.get("priority"),
                queue=filters.get("queue"),
                assignee=filters.get("assignee"),
                requester_id=filters.get("requester_id"),
                page=page,
                page_size=page_size,
            )
            total = self._repo.count_tickets(
                status=filters.get("status"),
                priority=filters.get("priority"),
                queue=filters.get("queue"),
                assignee=filters.get("assignee"),
            )
            return {
                "ok": True,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "items": [self._ticket_to_dict(t) for t in tickets],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                },
            }

        def execute_action(
            self,
            entity_id: str,
            action: str,
            operator_id: str,
            payload: dict[str, Any],
            trace_id: str,
        ) -> dict[str, Any]:
            now = datetime.now(UTC).isoformat()
            ticket = self._repo.get_ticket(entity_id)
            if ticket is None:
                return {
                    "ok": False,
                    "system": self.system_key,
                    "entity_type": self.entity_type,
                    "entity_id": entity_id,
                    "status": "error",
                    "error": {
                        "code": "entity_not_found",
                        "message": f"Ticket {entity_id} not found",
                    },
                    "updated_at": now,
                    "trace_id": trace_id,
                }

            next_status = self.next_status(action)
            if next_status is None:
                return {
                    "ok": False,
                    "system": self.system_key,
                    "entity_type": self.entity_type,
                    "entity_id": entity_id,
                    "status": ticket.status,
                    "error": {
                        "code": "forbidden_action",
                        "message": f"Unknown action: {action}",
                    },
                    "updated_at": now,
                    "trace_id": trace_id,
                }

            if not self.validate_transition(ticket.status, action):
                return {
                    "ok": False,
                    "system": self.system_key,
                    "entity_type": self.entity_type,
                    "entity_id": entity_id,
                    "status": ticket.status,
                    "error": {
                        "code": "invalid_state_transition",
                        "message": f"Cannot {action} from status {ticket.status}",
                        "details": {
                            "allowed_from": list(self.actions[action].allowed_from),
                        },
                    },
                    "updated_at": now,
                    "trace_id": trace_id,
                }

            update_data: dict[str, Any] = {"status": next_status}
            if action == "assign":
                update_data["assignee"] = payload.get("assignee_id")
            elif action == "escalate":
                update_data["escalated_at"] = datetime.now(UTC)
            elif action == "resolve":
                update_data["resolved_at"] = datetime.now(UTC)
                update_data["resolution_note"] = payload.get("resolution_note")
            elif action == "close":
                update_data["closed_at"] = datetime.now(UTC)
                update_data["close_reason"] = payload.get("close_reason")

            updated_ticket = self._repo.update_ticket(entity_id, **update_data)
            self._repo.add_event(
                ticket_id=entity_id,
                event_type=f"ticket_{action}",
                operator_id=operator_id,
                content=f"Ticket {action}d by {operator_id}",
                trace_id=trace_id,
                metadata=payload,
            )

            return {
                "ok": True,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": next_status,
                "updated_at": now,
                "trace_id": trace_id,
                "data": self._ticket_to_dict(updated_ticket) if updated_ticket else {},
            }

        def _ticket_to_dict(self, ticket: Any) -> dict[str, Any]:
            return {
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "status": ticket.status,
                "priority": ticket.priority,
                "channel": ticket.channel,
                "queue": ticket.queue,
                "assignee": ticket.assignee,
                "customer_id": ticket.customer_id,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            }

    return TicketSystem(ticket_repository)


class TicketSystem(BaseSystem):
    _repo: Any = None

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    @property
    def system_key(self) -> str:
        return "ticket"

    @property
    def entity_type(self) -> str:
        return "ticket"

    @property
    def id_prefix(self) -> str:
        return "T-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return TICKET_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "closed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return TICKET_ACTIONS

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        ticket = self._repo.create_ticket(
            channel=payload.get("channel", "api"),
            session_id=payload.get("session_id", ""),
            thread_id=payload.get("thread_id", ""),
            title=payload.get("title", ""),
            latest_message=payload.get("description", payload.get("latest_message", "")),
            intent=payload.get("intent", "general"),
            priority=payload.get("priority", "medium"),
            queue=payload.get("queue", "default"),
            customer_id=payload.get("customer_id"),
            assignee=payload.get("assignee"),
            metadata=payload.get("metadata"),
        )
        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "entity_id": ticket.ticket_id,
            "status": ticket.status,
            "created_at": now,
            "updated_at": now,
            "data": self._ticket_to_dict(ticket),
        }

    def get(self, entity_id: str) -> dict[str, Any] | None:
        ticket = self._repo.get_ticket(entity_id)
        if ticket is None:
            return None
        return self._ticket_to_dict(ticket)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        from datetime import UTC, datetime

        filters = filters or {}
        tickets = self._repo.list_tickets(
            status=filters.get("status"),
            priority=filters.get("priority"),
            queue=filters.get("queue"),
            assignee=filters.get("assignee"),
            requester_id=filters.get("requester_id"),
            page=page,
            page_size=page_size,
        )
        total = self._repo.count_tickets(
            status=filters.get("status"),
            priority=filters.get("priority"),
            queue=filters.get("queue"),
            assignee=filters.get("assignee"),
        )
        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "items": [self._ticket_to_dict(t) for t in tickets],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }

    def execute_action(
        self,
        entity_id: str,
        action: str,
        operator_id: str,
        payload: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        ticket = self._repo.get_ticket(entity_id)
        if ticket is None:
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": "error",
                "error": {"code": "entity_not_found", "message": f"Ticket {entity_id} not found"},
                "updated_at": now,
                "trace_id": trace_id,
            }

        next_status = self.next_status(action)
        if next_status is None:
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": ticket.status,
                "error": {"code": "forbidden_action", "message": f"Unknown action: {action}"},
                "updated_at": now,
                "trace_id": trace_id,
            }

        if not self.validate_transition(ticket.status, action):
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": ticket.status,
                "error": {
                    "code": "invalid_state_transition",
                    "message": f"Cannot {action} from status {ticket.status}",
                    "details": {"allowed_from": list(self.actions[action].allowed_from)},
                },
                "updated_at": now,
                "trace_id": trace_id,
            }

        update_data: dict[str, Any] = {"status": next_status}
        if action == "assign":
            update_data["assignee"] = payload.get("assignee_id")
        elif action == "escalate":
            update_data["escalated_at"] = datetime.now(UTC)
        elif action == "resolve":
            update_data["resolved_at"] = datetime.now(UTC)
            update_data["resolution_note"] = payload.get("resolution_note")
        elif action == "close":
            update_data["closed_at"] = datetime.now(UTC)
            update_data["close_reason"] = payload.get("close_reason")

        updated_ticket = self._repo.update_ticket(entity_id, **update_data)
        self._repo.add_event(
            ticket_id=entity_id,
            event_type=f"ticket_{action}",
            operator_id=operator_id,
            content=f"Ticket {action}d by {operator_id}",
            trace_id=trace_id,
            metadata=payload,
        )

        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "entity_id": entity_id,
            "status": next_status,
            "updated_at": now,
            "trace_id": trace_id,
            "data": self._ticket_to_dict(updated_ticket) if updated_ticket else {},
        }

    def _ticket_to_dict(self, ticket: Any) -> dict[str, Any]:
        return {
            "ticket_id": ticket.ticket_id,
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "channel": ticket.channel,
            "queue": ticket.queue,
            "assignee": ticket.assignee,
            "customer_id": ticket.customer_id,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        }
