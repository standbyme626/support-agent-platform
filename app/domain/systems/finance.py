from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.systems.base import BaseSystem, SystemAction


FINANCE_LIFECYCLE = (
    "invoice_received",
    "matching",
    "exception_flagged",
    "pending_review",
    "approved_for_payment",
    "paid",
    "settled",
)

FINANCE_ACTIONS = {
    "match": SystemAction(
        name="match",
        allowed_from=frozenset({"invoice_received"}),
        to_status="matching",
        required_fields=("match_reference",),
    ),
    "flag_exception": SystemAction(
        name="flag_exception",
        allowed_from=frozenset({"matching"}),
        to_status="exception_flagged",
        required_fields=("exception_reason",),
    ),
    "submit_review": SystemAction(
        name="submit_review",
        allowed_from=frozenset({"exception_flagged"}),
        to_status="pending_review",
        required_fields=("reviewer_id",),
    ),
    "approve_payment": SystemAction(
        name="approve_payment",
        allowed_from=frozenset({"pending_review"}),
        to_status="approved_for_payment",
        required_fields=("approver_id",),
    ),
    "mark_paid": SystemAction(
        name="mark_paid",
        allowed_from=frozenset({"approved_for_payment"}),
        to_status="paid",
        required_fields=("payment_txn_id",),
    ),
    "settle": SystemAction(
        name="settle",
        allowed_from=frozenset({"paid"}),
        to_status="settled",
        required_fields=("settlement_batch_id",),
    ),
}


class FinanceSystem(BaseSystem):
    def __init__(self) -> None:
        self._entities: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def system_key(self) -> str:
        return "finance"

    @property
    def entity_type(self) -> str:
        return "finance_invoice"

    @property
    def id_prefix(self) -> str:
        return "INV-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return FINANCE_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "settled"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return FINANCE_ACTIONS

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity_id = (
            f"{self.id_prefix}{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
        )
        entity = {
            "id": entity_id,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "status": "invoice_received",
            "vendor_id": payload.get("vendor_id"),
            "invoice_no": payload.get("invoice_no"),
            "po_no": payload.get("po_no"),
            "receipt_no": payload.get("receipt_no"),
            "amount": payload.get("amount"),
            "currency": payload.get("currency", "CNY"),
            "invoice_date": payload.get("invoice_date"),
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
            "status": "invoice_received",
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
                "error": {"code": "entity_not_found", "message": f"Invoice {entity_id} not found"},
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
