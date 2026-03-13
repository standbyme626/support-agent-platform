from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from app.domain.ticket.ticket_workflow_state import TicketWorkflowState

CloseAction = Literal["customer_confirm", "operator_close"]


@dataclass(frozen=True)
class TicketActionResult:
    ticket_id: str
    status: str
    handoff_state: str
    event_type: str
    message: str


@dataclass(frozen=True)
class SessionActionResult:
    session_id: str
    actor_id: str
    reason: str
    event_type: str
    message: str


class TicketRepositoryProtocol(Protocol):
    def get_workflow_state(self, ticket_id: str) -> TicketWorkflowState: ...

    def update_ticket_fields(self, ticket_id: str, fields: dict[str, Any]) -> None: ...

    def append_event(self, ticket_id: str, event_type: str, payload: dict[str, Any]) -> None: ...


class SessionServiceProtocol(Protocol):
    def mark_waiting_customer(self, session_id: str, ticket_id: str, flag: bool) -> Any: ...

    def clear_active_ticket(self, session_id: str) -> Any: ...

    def end_session(self, session_id: str) -> Any: ...


class TicketAPI:
    """Upgrade 5 domain ticket actions with explicit close semantics."""

    def __init__(self, ticket_repo: TicketRepositoryProtocol, session_service: SessionServiceProtocol) -> None:
        self._ticket_repo = ticket_repo
        self._session_service = session_service

    def resolve(
        self,
        ticket_id: str,
        *,
        actor_id: str,
        resolution_note: str,
        resolution_code: str | None = None,
        session_id: str | None = None,
    ) -> TicketActionResult:
        state = self._ticket_repo.get_workflow_state(ticket_id)
        if not state.can_resolve():
            raise ValueError(f"ticket {ticket_id} cannot be resolved from status={state.status}")

        self._ticket_repo.update_ticket_fields(
            ticket_id,
            {
                "status": "resolved",
                "handoff_state": "waiting_customer",
                "needs_handoff": False,
                "latest_message": resolution_note,
                "resolution_note": resolution_note,
                "resolution_code": resolution_code,
                "resolved_at": datetime.now(UTC),
                "lifecycle_stage": "resolved",
                "last_agent_action": "resolve",
            },
        )
        self._ticket_repo.append_event(
            ticket_id,
            "ticket_resolved",
            self._audit_payload(
                actor_id=actor_id,
                action="resolve",
                resolution_note=resolution_note,
                resolution_code=resolution_code,
                previous_status=state.status,
                previous_handoff_state=state.handoff_state,
            ),
        )

        if session_id is not None:
            self._session_service.mark_waiting_customer(session_id, ticket_id, True)

        return TicketActionResult(
            ticket_id=ticket_id,
            status="resolved",
            handoff_state="waiting_customer",
            event_type="ticket_resolved",
            message="Ticket resolved and waiting for customer confirmation.",
        )

    def customer_confirm(
        self,
        ticket_id: str,
        *,
        actor_id: str,
        note: str | None = None,
        session_id: str | None = None,
    ) -> TicketActionResult:
        state = self._ticket_repo.get_workflow_state(ticket_id)
        if not state.can_customer_confirm():
            raise ValueError(f"ticket {ticket_id} cannot be customer-confirmed")

        self._ticket_repo.update_ticket_fields(
            ticket_id,
            {
                "status": "closed",
                "handoff_state": "completed",
                "close_reason": "customer_confirmed",
                "closed_at": datetime.now(UTC),
                "lifecycle_stage": "closed",
                "last_agent_action": "customer_confirm",
            },
        )
        self._ticket_repo.append_event(
            ticket_id,
            "ticket_customer_confirmed",
            self._audit_payload(
                actor_id=actor_id,
                action="customer_confirm",
                note=note,
                close_reason="customer_confirmed",
                previous_status=state.status,
                previous_handoff_state=state.handoff_state,
            ),
        )

        if session_id is not None:
            self._session_service.clear_active_ticket(session_id)

        return TicketActionResult(
            ticket_id=ticket_id,
            status="closed",
            handoff_state="completed",
            event_type="ticket_customer_confirmed",
            message="Ticket closed after customer confirmation.",
        )

    def operator_close(
        self,
        ticket_id: str,
        *,
        actor_id: str,
        reason: str | None = None,
        note: str | None = None,
        session_id: str | None = None,
    ) -> TicketActionResult:
        state = self._ticket_repo.get_workflow_state(ticket_id)
        if not state.can_operator_close():
            raise ValueError(f"ticket {ticket_id} cannot be operator-closed")

        close_reason = reason or "operator_forced_close"
        self._ticket_repo.update_ticket_fields(
            ticket_id,
            {
                "status": "closed",
                "handoff_state": "completed",
                "close_reason": close_reason,
                "closed_at": datetime.now(UTC),
                "lifecycle_stage": "closed",
                "last_agent_action": "operator_close",
            },
        )
        self._ticket_repo.append_event(
            ticket_id,
            "ticket_operator_closed",
            self._audit_payload(
                actor_id=actor_id,
                action="operator_close",
                reason=close_reason,
                note=note,
                previous_status=state.status,
                previous_handoff_state=state.handoff_state,
            ),
        )

        if session_id is not None:
            self._session_service.clear_active_ticket(session_id)

        return TicketActionResult(
            ticket_id=ticket_id,
            status="closed",
            handoff_state="completed",
            event_type="ticket_operator_closed",
            message="Ticket forcibly closed by operator.",
        )

    def end_session(
        self,
        session_id: str,
        *,
        actor_id: str,
        reason: str | None = None,
    ) -> SessionActionResult:
        resolved_reason = reason or "manual_end"
        self._session_service.end_session(session_id)
        return SessionActionResult(
            session_id=session_id,
            actor_id=actor_id,
            reason=resolved_reason,
            event_type="session_ended",
            message="Session ended successfully.",
        )

    def close(
        self,
        ticket_id: str,
        *,
        actor_id: str,
        action: CloseAction | None = None,
        session_id: str | None = None,
        note: str | None = None,
        reason: str | None = None,
    ) -> TicketActionResult:
        """Compatibility entry for v1 /close with explicit routing."""
        if action is None:
            raise ValueError(
                "ambiguous close action; specify action='customer_confirm' or action='operator_close'"
            )
        if action == "customer_confirm":
            return self.customer_confirm(
                ticket_id,
                actor_id=actor_id,
                note=note,
                session_id=session_id,
            )
        return self.operator_close(
            ticket_id,
            actor_id=actor_id,
            reason=reason,
            note=note,
            session_id=session_id,
        )

    @staticmethod
    def _audit_payload(
        *,
        actor_id: str,
        action: str,
        note: str | None = None,
        reason: str | None = None,
        resolution_note: str | None = None,
        resolution_code: str | None = None,
        close_reason: str | None = None,
        previous_status: str | None = None,
        previous_handoff_state: str | None = None,
    ) -> dict[str, Any]:
        return {
            "actor_id": actor_id,
            "action": action,
            "note": note,
            "reason": reason,
            "resolution_note": resolution_note,
            "resolution_code": resolution_code,
            "close_reason": close_reason,
            "previous_status": previous_status,
            "previous_handoff_state": previous_handoff_state,
            "occurred_at": datetime.now(UTC).isoformat(),
        }
