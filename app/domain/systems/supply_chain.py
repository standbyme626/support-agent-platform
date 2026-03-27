from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.systems.base import BaseSystem, SystemAction

if TYPE_CHECKING:
    from storage.systems_repository import SupplyChainRepository


SUPPLY_CHAIN_LIFECYCLE = (
    "awaiting_receipt",
    "received",
    "stocked",
    "allocated",
    "fulfilled",
    "returned",
    "closed",
)

SUPPLY_CHAIN_ACTIONS = {
    "receive": SystemAction(
        name="receive",
        allowed_from=frozenset({"awaiting_receipt"}),
        to_status="received",
        required_fields=("receipt_qty",),
    ),
    "stock": SystemAction(
        name="stock",
        allowed_from=frozenset({"received"}),
        to_status="stocked",
        required_fields=("location",),
    ),
    "allocate": SystemAction(
        name="allocate",
        allowed_from=frozenset({"stocked"}),
        to_status="allocated",
        required_fields=("order_id",),
    ),
    "fulfill": SystemAction(
        name="fulfill",
        allowed_from=frozenset({"allocated"}),
        to_status="fulfilled",
        required_fields=("shipment_id",),
    ),
    "return": SystemAction(
        name="return",
        allowed_from=frozenset({"fulfilled"}),
        to_status="returned",
        required_fields=("return_reason",),
    ),
    "close": SystemAction(
        name="close",
        allowed_from=frozenset({"fulfilled", "returned"}),
        to_status="closed",
        required_fields=(),
    ),
}


class SupplyChainSystem(BaseSystem):
    def __init__(self, repo: "SupplyChainRepository | None" = None) -> None:
        if repo is None:
            from storage.systems_repository import SupplyChainRepository

            repo = SupplyChainRepository(Path("storage/systems.db"))
            repo.apply_migrations()
        self._repo = repo

    @property
    def system_key(self) -> str:
        return "supply_chain"

    @property
    def entity_type(self) -> str:
        return "supply_chain_order"

    @property
    def id_prefix(self) -> str:
        return "SC-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return SUPPLY_CHAIN_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "completed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return SUPPLY_CHAIN_ACTIONS

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity = self._repo.create(payload)
        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "entity_id": entity["id"],
            "status": entity["status"],
            "created_at": entity["created_at"],
            "updated_at": entity["updated_at"],
            "data": entity,
        }

    def get(self, entity_id: str) -> dict[str, Any] | None:
        return self._repo.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        items, total = self._repo.list(filters, page, page_size)
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
        entity = self._repo.get(entity_id)

        if entity is None:
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": "error",
                "error": {"code": "entity_not_found", "message": f"Order {entity_id} not found"},
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

        update_data: dict[str, Any] = {"status": next_status}
        if action == "deliver":
            update_data["received_at"] = now

        updated = self._repo.update(entity_id, update_data)

        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "entity_id": entity_id,
            "status": next_status,
            "updated_at": now,
            "trace_id": trace_id,
            "data": updated,
        }
