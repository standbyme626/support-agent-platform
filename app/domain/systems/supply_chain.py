from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.systems.base import BaseSystem, SystemAction

if TYPE_CHECKING:
    from storage.systems_repository import SupplyChainRepository


SUPPLY_CHAIN_LIFECYCLE = (
    "pending",
    "confirmed",
    "shipped",
    "in_transit",
    "delivered",
    "completed",
)

SUPPLY_CHAIN_ACTIONS = {
    "confirm": SystemAction(
        name="confirm",
        allowed_from=frozenset({"pending"}),
        to_status="confirmed",
        required_fields=(),
    ),
    "ship": SystemAction(
        name="ship",
        allowed_from=frozenset({"confirmed"}),
        to_status="shipped",
        required_fields=("tracking_no",),
    ),
    "in_transit": SystemAction(
        name="in_transit",
        allowed_from=frozenset({"shipped"}),
        to_status="in_transit",
        required_fields=(),
    ),
    "deliver": SystemAction(
        name="deliver",
        allowed_from=frozenset({"in_transit"}),
        to_status="delivered",
        required_fields=(),
    ),
    "complete": SystemAction(
        name="complete",
        allowed_from=frozenset({"delivered"}),
        to_status="completed",
        required_fields=(),
    ),
    "cancel": SystemAction(
        name="cancel",
        allowed_from=frozenset({"pending", "confirmed"}),
        to_status="pending",
        required_fields=("cancel_reason",),
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
