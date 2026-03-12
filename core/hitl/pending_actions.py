from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from storage.models import Ticket

PendingApprovalStatus = Literal["pending_approval", "approved", "rejected", "timeout"]

PENDING_ACTIONS_KEY = "pending_actions"
DEFAULT_APPROVAL_TTL_MINUTES = 30


@dataclass(frozen=True)
class PendingAction:
    approval_id: str
    ticket_id: str
    action_type: str
    risk_level: str
    status: PendingApprovalStatus
    requested_by: str
    requested_at: str
    timeout_at: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    approved_by: str | None = None
    rejected_by: str | None = None
    decided_at: str | None = None
    decision_note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "ticket_id": self.ticket_id,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "status": self.status,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at,
            "timeout_at": self.timeout_at,
            "reason": self.reason,
            "payload": dict(self.payload),
            "context": dict(self.context),
            "approved_by": self.approved_by,
            "rejected_by": self.rejected_by,
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
        }


def build_pending_action(
    *,
    ticket_id: str,
    action_type: str,
    risk_level: str,
    requested_by: str,
    reason: str,
    payload: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    timeout_minutes: int = DEFAULT_APPROVAL_TTL_MINUTES,
) -> PendingAction:
    now = datetime.now(UTC)
    safe_timeout = max(0, timeout_minutes)
    timeout_at = now + timedelta(minutes=safe_timeout)
    return PendingAction(
        approval_id=f"apr_{uuid.uuid4().hex[:12]}",
        ticket_id=ticket_id,
        action_type=action_type,
        risk_level=risk_level,
        status="pending_approval",
        requested_by=requested_by,
        requested_at=now.isoformat(),
        timeout_at=timeout_at.isoformat(),
        reason=reason,
        payload=dict(payload or {}),
        context=dict(context or {}),
    )


def load_pending_actions(ticket: Ticket) -> list[PendingAction]:
    raw = ticket.metadata.get(PENDING_ACTIONS_KEY)
    if not isinstance(raw, list):
        return []

    actions: list[PendingAction] = []
    for item in raw:
        parsed = _parse_pending_action(item, ticket_id=ticket.ticket_id)
        if parsed is not None:
            actions.append(parsed)
    return actions


def save_pending_actions(
    metadata: dict[str, Any], actions: Iterable[PendingAction]
) -> dict[str, Any]:
    serialized = [item.as_dict() for item in actions]
    next_metadata = dict(metadata)
    next_metadata[PENDING_ACTIONS_KEY] = serialized
    open_actions = [item for item in serialized if item.get("status") == "pending_approval"]
    next_metadata["approval_required"] = bool(open_actions)
    next_metadata["latest_pending_approval_id"] = (
        str(open_actions[-1]["approval_id"]) if open_actions else None
    )
    return next_metadata


def find_action(actions: Iterable[PendingAction], approval_id: str) -> PendingAction | None:
    for item in actions:
        if item.approval_id == approval_id:
            return item
    return None


def replace_action(
    actions: Iterable[PendingAction], *, approval_id: str, next_action: PendingAction
) -> list[PendingAction]:
    updated: list[PendingAction] = []
    replaced = False
    for item in actions:
        if item.approval_id == approval_id:
            updated.append(next_action)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(next_action)
    return updated


def is_action_timed_out(action: PendingAction, *, now: datetime | None = None) -> bool:
    if action.status != "pending_approval":
        return False
    parsed_timeout = _parse_iso_datetime(action.timeout_at)
    if parsed_timeout is None:
        return False
    return parsed_timeout <= (now or datetime.now(UTC))


def _parse_pending_action(raw: object, *, ticket_id: str) -> PendingAction | None:
    if not isinstance(raw, dict):
        return None
    approval_id = str(raw.get("approval_id") or "").strip()
    action_type = str(raw.get("action_type") or "").strip()
    status = str(raw.get("status") or "pending_approval").strip()
    if not approval_id or not action_type:
        return None
    if status not in {"pending_approval", "approved", "rejected", "timeout"}:
        status = "pending_approval"
    payload = raw.get("payload")
    context = raw.get("context")
    return PendingAction(
        approval_id=approval_id,
        ticket_id=str(raw.get("ticket_id") or ticket_id),
        action_type=action_type,
        risk_level=str(raw.get("risk_level") or "high"),
        status=status,  # type: ignore[arg-type]
        requested_by=str(raw.get("requested_by") or "unknown"),
        requested_at=str(raw.get("requested_at") or datetime.now(UTC).isoformat()),
        timeout_at=str(raw.get("timeout_at") or datetime.now(UTC).isoformat()),
        reason=str(raw.get("reason") or action_type),
        payload=dict(payload) if isinstance(payload, dict) else {},
        context=dict(context) if isinstance(context, dict) else {},
        approved_by=_optional_str(raw.get("approved_by")),
        rejected_by=_optional_str(raw.get("rejected_by")),
        decided_at=_optional_str(raw.get("decided_at")),
        decision_note=_optional_str(raw.get("decision_note")),
    )


def _optional_str(raw: object) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _parse_iso_datetime(raw: object) -> datetime | None:
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
