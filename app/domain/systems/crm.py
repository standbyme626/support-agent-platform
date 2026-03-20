from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.systems.base import BaseSystem, SystemAction

if TYPE_CHECKING:
    from storage.systems_repository import CrmRepository


CRM_LIFECYCLE = (
    "new",
    "assigned",
    "in_progress",
    "resolved",
    "closed",
)

CRM_ACTIONS = {
    "assign": SystemAction(
        name="assign",
        allowed_from=frozenset({"new"}),
        to_status="assigned",
        required_fields=("assigned_to",),
    ),
    "work_on": SystemAction(
        name="work_on",
        allowed_from=frozenset({"assigned"}),
        to_status="in_progress",
        required_fields=(),
    ),
    "resolve": SystemAction(
        name="resolve",
        allowed_from=frozenset({"in_progress"}),
        to_status="resolved",
        required_fields=("resolution",),
    ),
    "close": SystemAction(
        name="close",
        allowed_from=frozenset({"resolved"}),
        to_status="closed",
        required_fields=(),
    ),
    "reopen": SystemAction(
        name="reopen",
        allowed_from=frozenset({"resolved", "closed"}),
        to_status="new",
        required_fields=("reopen_reason",),
    ),
}


class CrmSystem(BaseSystem):
    def __init__(self, repo: "CrmRepository | None" = None) -> None:
        if repo is None:
            from storage.systems_repository import CrmRepository

            repo = CrmRepository(Path("storage/systems.db"))
            repo.apply_migrations()
        self._repo = repo

    @property
    def system_key(self) -> str:
        return "crm"

    @property
    def entity_type(self) -> str:
        return "crm_case"

    @property
    def id_prefix(self) -> str:
        return "CRM-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return CRM_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "closed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return CRM_ACTIONS

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
            "pagination": {"Page": page, "page_size": page_size, "total": total},
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
                "error": {"code": "entity_not_found", "message": f"Case {entity_id} not found"},
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
        if action == "assign":
            update_data["assigned_to"] = payload.get("assigned_to")
        elif action == "resolve":
            update_data["resolution"] = payload.get("resolution")

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
