from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.systems.base import BaseSystem, SystemAction


PROCUREMENT_LIFECYCLE = (
    "draft",
    "pending_approval",
    "approved",
    "ordered",
    "received",
    "invoiced",
    "completed",
)

PROCUREMENT_ACTIONS = {
    "submit": SystemAction(
        name="submit",
        allowed_from=frozenset({"draft"}),
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
        to_status="draft",
        required_fields=("reject_reason",),
    ),
    "order": SystemAction(
        name="order",
        allowed_from=frozenset({"approved"}),
        to_status="ordered",
        required_fields=("po_no", "supplier_id"),
    ),
    "receive": SystemAction(
        name="receive",
        allowed_from=frozenset({"ordered"}),
        to_status="received",
        required_fields=("received_qty",),
    ),
    "invoice": SystemAction(
        name="invoice",
        allowed_from=frozenset({"received"}),
        to_status="invoiced",
        required_fields=("invoice_ref",),
    ),
    "complete": SystemAction(
        name="complete",
        allowed_from=frozenset({"received", "invoiced"}),
        to_status="completed",
        required_fields=(),
    ),
}


class ProcurementSystem(BaseSystem):
    def __init__(self) -> None:
        self._entities: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def system_key(self) -> str:
        return "procurement"

    @property
    def entity_type(self) -> str:
        return "procurement_request"

    @property
    def id_prefix(self) -> str:
        return "PR-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return PROCUREMENT_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "completed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return PROCUREMENT_ACTIONS

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity_id = (
            f"{self.id_prefix}{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
        )
        entity = {
            "id": entity_id,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "status": "draft",
            "requester_id": payload.get("requester_id"),
            "item_name": payload.get("item_name"),
            "category": payload.get("category"),
            "quantity": payload.get("quantity"),
            "budget": payload.get("budget"),
            "business_reason": payload.get("business_reason"),
            "urgency": payload.get("urgency", "normal"),
            "approver_id": None,
            "supplier_id": None,
            "po_no": None,
            "received_qty": None,
            "invoice_ref": None,
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
            "status": "draft",
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
        if "requester_id" in filters:
            results = [e for e in results if e.get("requester_id") == filters["requester_id"]]

        total = len(results)
        offset = (page - 1) * page_size
        items = results[offset : offset + page_size]

        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "items": items,
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
                "error": {"code": "entity_not_found", "message": f"Request {entity_id} not found"},
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

        update_data: dict[str, Any] = {"status": next_status, "updated_at": now}
        if action == "approve":
            update_data["approver_id"] = payload.get("approver_id")
        elif action == "reject":
            update_data["reject_reason"] = payload.get("reject_reason")
        elif action == "order":
            update_data["po_no"] = payload.get("po_no")
            update_data["supplier_id"] = payload.get("supplier_id")
        elif action == "receive":
            update_data["received_qty"] = payload.get("received_qty")
        elif action == "invoice":
            update_data["invoice_ref"] = payload.get("invoice_ref")

        entity.update(update_data)
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
