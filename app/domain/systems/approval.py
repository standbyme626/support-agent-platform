from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.systems.base import BaseSystem, SystemAction


APPROVAL_LIFECYCLE = (
    "submitted",
    "pending_approval",
    "returned_for_info",
    "approved",
    "rejected",
    "archived",
)

APPROVAL_ACTIONS = {
    "submit": SystemAction(
        name="submit",
        allowed_from=frozenset({"submitted"}),
        to_status="pending_approval",
        required_fields=(),
    ),
    "approve": SystemAction(
        name="approve",
        allowed_from=frozenset({"pending_approval"}),
        to_status="approved",
        required_fields=("approver_id",),
    ),
    "reject": SystemAction(
        name="reject",
        allowed_from=frozenset({"pending_approval"}),
        to_status="rejected",
        required_fields=("reject_reason",),
    ),
    "return_for_info": SystemAction(
        name="return_for_info",
        allowed_from=frozenset({"pending_approval"}),
        to_status="returned_for_info",
        required_fields=("missing_items",),
    ),
    "archive": SystemAction(
        name="archive",
        allowed_from=frozenset({"approved", "rejected"}),
        to_status="archived",
        required_fields=("archive_reason",),
    ),
}


class ApprovalSystem(BaseSystem):
    def __init__(self) -> None:
        self._entities: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def system_key(self) -> str:
        return "approval"

    @property
    def entity_type(self) -> str:
        return "approval_request"

    @property
    def id_prefix(self) -> str:
        return "AP-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return APPROVAL_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "archived"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return APPROVAL_ACTIONS

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity_id = (
            f"{self.id_prefix}{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
        )
        entity = {
            "id": entity_id,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "status": "submitted",
            "request_type": payload.get("request_type"),
            "requester_id": payload.get("requester_id"),
            "title": payload.get("title"),
            "content": payload.get("content"),
            "attachments": payload.get("attachments", []),
            "approver_chain": payload.get("approver_chain", []),
            "created_at": now,
            "updated_at": now,
        }
        self._entities[entity_id] = entity
        self._add_event(entity_id, "created", {}, now)
        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "entity_id": entity_id,
            "status": "submitted",
            "created_at": now,
            "updated_at": now,
            "data": entity,
        }

    def get(self, entity_id: str) -> dict[str, Any] | None:
        return self._entities.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        filters = filters or {}
        results = list(self._entities.values())
        if "status" in filters:
            results = [e for e in results if e["status"] == filters["status"]]
        total = len(results)
        offset = (page - 1) * page_size
        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "items": results[offset : offset + page_size],
            "pagination": {"page": page, "page_size": page_size, "total": total},
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
        entity = self._entities.get(entity_id)

        if entity is None:
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": "error",
                "error": {"code": "entity_not_found", "message": f"Approval {entity_id} not found"},
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
                "status": entity["status"],
                "error": {"code": "forbidden_action", "message": f"Unknown action: {action}"},
                "updated_at": now,
                "trace_id": trace_id,
            }

        if not self.validate_transition(entity["status"], action):
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": entity["status"],
                "error": {
                    "code": "invalid_state_transition",
                    "message": f"Cannot {action} from status {entity['status']}",
                    "details": {"allowed_from": list(self.actions[action].allowed_from)},
                },
                "updated_at": now,
                "trace_id": trace_id,
            }

        entity.update({"status": next_status, "updated_at": now})
        self._add_event(entity_id, action, payload, now)

        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "entity_id": entity_id,
            "status": next_status,
            "updated_at": now,
            "trace_id": trace_id,
            "data": entity,
        }

    def _add_event(
        self, entity_id: str, action: str, payload: dict[str, Any], timestamp: str
    ) -> None:
        self._events.append(
            {
                "id": str(uuid.uuid4()),
                "entity_id": entity_id,
                "action": action,
                "payload": payload,
                "timestamp": timestamp,
            }
        )
