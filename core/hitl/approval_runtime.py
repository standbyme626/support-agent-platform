from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from core.ticket_api import TicketAPI
from core.trace_logger import JsonTraceLogger
from storage.models import Ticket

from .approval_policy import ApprovalPolicy, ApprovalRequirement
from .pending_actions import (
    PendingAction,
    build_pending_action,
    find_action,
    is_action_timed_out,
    load_pending_actions,
    replace_action,
    save_pending_actions,
)


@dataclass(frozen=True)
class ApprovalRequestResult:
    requires_approval: bool
    ticket: Ticket
    requirement: ApprovalRequirement
    pending_action: PendingAction | None = None


@dataclass(frozen=True)
class ApprovalDecisionResult:
    ticket: Ticket
    pending_action: PendingAction


class ApprovalRuntime:
    """Runtime helper for approval request/decision lifecycle."""

    def __init__(
        self,
        *,
        ticket_api: TicketAPI,
        policy: ApprovalPolicy | None = None,
        trace_logger: JsonTraceLogger | None = None,
    ) -> None:
        self._ticket_api = ticket_api
        self._policy = policy or ApprovalPolicy.default()
        self._trace_logger = trace_logger

    def request_approval_if_needed(
        self,
        *,
        ticket_id: str,
        action_type: str,
        actor_id: str,
        payload: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
        timeout_minutes: int | None = None,
        trace_id: str | None = None,
    ) -> ApprovalRequestResult:
        ticket = self._ticket_api.require_ticket(ticket_id)
        payload_dict = dict(payload or {})
        requirement = self._policy.evaluate(
            action_type=action_type, ticket=ticket, payload=payload_dict
        )
        if not requirement.requires_approval:
            return ApprovalRequestResult(
                requires_approval=False,
                ticket=ticket,
                requirement=requirement,
                pending_action=None,
            )

        requested_timeout = timeout_minutes
        if requested_timeout is None:
            raw_timeout = payload_dict.get("timeout_minutes")
            if isinstance(raw_timeout, int):
                requested_timeout = raw_timeout
        pending_action = build_pending_action(
            ticket_id=ticket.ticket_id,
            action_type=action_type,
            risk_level=requirement.risk_level,
            requested_by=actor_id,
            reason=requirement.reason,
            payload=payload_dict,
            context=dict(context or {}),
            timeout_minutes=requested_timeout if requested_timeout is not None else 30,
        )
        all_actions = load_pending_actions(ticket)
        all_actions.append(pending_action)
        next_metadata = save_pending_actions(ticket.metadata, all_actions)
        updated = self._ticket_api.update_ticket(
            ticket_id,
            {
                "handoff_state": "pending_approval",
                "risk_level": requirement.risk_level,
                "last_agent_action": f"approval_pending:{action_type}",
                "metadata": next_metadata,
            },
            actor_id=actor_id,
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="approval_requested",
            actor_type="agent",
            actor_id=actor_id,
            payload={
                **pending_action.as_dict(),
                "policy_version": requirement.policy_version,
                "rule_id": requirement.rule_id,
            },
        )
        self._log_trace(
            "approval_requested",
            {
                "approval_id": pending_action.approval_id,
                "action_type": action_type,
                "ticket_id": ticket_id,
                "requested_by": actor_id,
                "rule_id": requirement.rule_id,
                "policy_version": requirement.policy_version,
            },
            trace_id=trace_id or _ticket_trace_id(updated),
            ticket=updated,
        )
        return ApprovalRequestResult(
            requires_approval=True,
            ticket=updated,
            requirement=requirement,
            pending_action=pending_action,
        )

    def list_pending_actions(self, *, ticket_id: str | None = None) -> list[PendingAction]:
        tickets = (
            [self._ticket_api.require_ticket(ticket_id)] if ticket_id else self._scan_tickets()
        )
        actions: list[PendingAction] = []
        for ticket in tickets:
            self._apply_timeouts(ticket)
            refreshed = self._ticket_api.require_ticket(ticket.ticket_id)
            for item in load_pending_actions(refreshed):
                if item.status == "pending_approval":
                    actions.append(item)
        actions.sort(key=lambda item: item.requested_at, reverse=True)
        return actions

    def list_ticket_actions(self, ticket_id: str) -> list[PendingAction]:
        ticket = self._ticket_api.require_ticket(ticket_id)
        self._apply_timeouts(ticket)
        refreshed = self._ticket_api.require_ticket(ticket_id)
        actions = load_pending_actions(refreshed)
        actions.sort(key=lambda item: item.requested_at, reverse=True)
        return actions

    def get_pending_action(self, approval_id: str) -> tuple[Ticket, PendingAction]:
        for ticket in self._scan_tickets():
            self._apply_timeouts(ticket)
            refreshed = self._ticket_api.require_ticket(ticket.ticket_id)
            actions = load_pending_actions(refreshed)
            matched = find_action(actions, approval_id)
            if matched is None:
                continue
            return refreshed, matched
        raise KeyError(f"approval {approval_id} not found")

    def mark_approved(
        self,
        approval_id: str,
        *,
        actor_id: str,
        execution_ticket: Ticket,
        note: str | None = None,
        trace_id: str | None = None,
    ) -> ApprovalDecisionResult:
        ticket, target = self.get_pending_action(approval_id)
        if target.status != "pending_approval":
            raise RuntimeError(f"approval {approval_id} is already {target.status}")

        now = datetime.now(UTC).isoformat()
        approved = replace(
            target,
            status="approved",
            approved_by=actor_id,
            decided_at=now,
            decision_note=note,
        )
        all_actions = replace_action(
            load_pending_actions(ticket), approval_id=approval_id, next_action=approved
        )
        open_actions = [item for item in all_actions if item.status == "pending_approval"]
        resume_state = _resume_handoff_state(target, fallback=execution_ticket.handoff_state)
        updated = self._ticket_api.update_ticket(
            execution_ticket.ticket_id,
            {
                "handoff_state": resume_state
                if not open_actions
                else execution_ticket.handoff_state,
                "last_agent_action": f"approval_approved:{target.action_type}",
                "metadata": save_pending_actions(execution_ticket.metadata, all_actions),
            },
            actor_id=actor_id,
        )
        self._ticket_api.add_event(
            updated.ticket_id,
            event_type="approval_decision",
            actor_type="agent",
            actor_id=actor_id,
            payload={
                "approval_id": approval_id,
                "action_type": target.action_type,
                "status": "approved",
                "approved_by": actor_id,
                "requested_by": target.requested_by,
                "decision_note": note,
            },
        )
        self._ticket_api.add_event(
            updated.ticket_id,
            event_type="approval_resumed",
            actor_type="agent",
            actor_id=actor_id,
            payload={
                "approval_id": approval_id,
                "action_type": target.action_type,
                "resume_handoff_state": resume_state,
            },
        )
        self._log_trace(
            "approval_decision",
            {
                "approval_id": approval_id,
                "action_type": target.action_type,
                "status": "approved",
                "approved_by": actor_id,
                "requested_by": target.requested_by,
            },
            trace_id=trace_id or _ticket_trace_id(updated),
            ticket=updated,
        )
        return ApprovalDecisionResult(ticket=updated, pending_action=approved)

    def mark_rejected(
        self,
        approval_id: str,
        *,
        actor_id: str,
        note: str | None = None,
        trace_id: str | None = None,
    ) -> ApprovalDecisionResult:
        ticket, target = self.get_pending_action(approval_id)
        if target.status != "pending_approval":
            raise RuntimeError(f"approval {approval_id} is already {target.status}")

        now = datetime.now(UTC).isoformat()
        rejected = replace(
            target,
            status="rejected",
            rejected_by=actor_id,
            decided_at=now,
            decision_note=note,
        )
        all_actions = replace_action(
            load_pending_actions(ticket), approval_id=approval_id, next_action=rejected
        )
        open_actions = [item for item in all_actions if item.status == "pending_approval"]
        resume_state = _resume_handoff_state(target, fallback=ticket.handoff_state)
        updated = self._ticket_api.update_ticket(
            ticket.ticket_id,
            {
                "handoff_state": resume_state if not open_actions else ticket.handoff_state,
                "last_agent_action": f"approval_rejected:{target.action_type}",
                "metadata": save_pending_actions(ticket.metadata, all_actions),
            },
            actor_id=actor_id,
        )
        self._ticket_api.add_event(
            updated.ticket_id,
            event_type="approval_decision",
            actor_type="agent",
            actor_id=actor_id,
            payload={
                "approval_id": approval_id,
                "action_type": target.action_type,
                "status": "rejected",
                "rejected_by": actor_id,
                "requested_by": target.requested_by,
                "decision_note": note,
            },
        )
        self._log_trace(
            "approval_decision",
            {
                "approval_id": approval_id,
                "action_type": target.action_type,
                "status": "rejected",
                "rejected_by": actor_id,
                "requested_by": target.requested_by,
            },
            trace_id=trace_id or _ticket_trace_id(updated),
            ticket=updated,
        )
        return ApprovalDecisionResult(ticket=updated, pending_action=rejected)

    def _apply_timeouts(self, ticket: Ticket) -> None:
        actions = load_pending_actions(ticket)
        if not actions:
            return
        timed_out: list[PendingAction] = []
        changed = False
        now = datetime.now(UTC)
        timeout_targets: list[PendingAction] = []
        for item in actions:
            if not is_action_timed_out(item, now=now):
                timed_out.append(item)
                continue
            changed = True
            timeout_item = replace(
                item,
                status="timeout",
                decided_at=now.isoformat(),
                decision_note="approval_timeout",
            )
            timed_out.append(timeout_item)
            timeout_targets.append(timeout_item)
        if not changed:
            return
        open_actions = [item for item in timed_out if item.status == "pending_approval"]
        latest_timeout = timeout_targets[-1] if timeout_targets else None
        next_ticket = self._ticket_api.update_ticket(
            ticket.ticket_id,
            {
                "handoff_state": (
                    _resume_handoff_state(latest_timeout, fallback=ticket.handoff_state)
                    if not open_actions
                    else ticket.handoff_state
                ),
                "last_agent_action": "approval_timeout",
                "metadata": save_pending_actions(ticket.metadata, timed_out),
            },
            actor_id="approval-runtime",
        )
        if latest_timeout is None:
            return
        self._ticket_api.add_event(
            ticket.ticket_id,
            event_type="approval_decision",
            actor_type="system",
            actor_id="approval-runtime",
            payload={
                "approval_id": latest_timeout.approval_id,
                "action_type": latest_timeout.action_type,
                "status": "timeout",
                "requested_by": latest_timeout.requested_by,
            },
        )
        self._log_trace(
            "approval_decision",
            {
                "approval_id": latest_timeout.approval_id,
                "action_type": latest_timeout.action_type,
                "status": "timeout",
                "requested_by": latest_timeout.requested_by,
            },
            trace_id=_ticket_trace_id(next_ticket),
            ticket=next_ticket,
        )

    def _scan_tickets(self) -> list[Ticket]:
        return self._ticket_api.list_all_tickets(limit=5000)

    def _log_trace(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        trace_id: str | None,
        ticket: Ticket,
    ) -> None:
        if self._trace_logger is None or not trace_id:
            return
        self._trace_logger.log(
            event_type,
            payload,
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=ticket.session_id,
        )


def _ticket_trace_id(ticket: Ticket) -> str | None:
    raw = ticket.metadata.get("trace_id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _resume_handoff_state(action: PendingAction | None, *, fallback: str) -> str:
    if action is None:
        return fallback
    raw = action.context.get("resume_handoff_state")
    if raw is None:
        return fallback
    value = str(raw).strip()
    return value or fallback
