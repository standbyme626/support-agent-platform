from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.systems.base import BaseSystem, SystemAction

if TYPE_CHECKING:
    from storage.systems_repository import HrRepository


HR_LIFECYCLE = (
    "preboarding",
    "submitted",
    "pending_approval",
    "profile_created",
    "provisioning",
    "active",
    "completed",
)

HR_ACTIONS = {
    "send_offer": SystemAction(
        name="send_offer",
        allowed_from=frozenset({"preboarding"}),
        to_status="submitted",
        required_fields=("candidate_name", "position"),
    ),
    "submit": SystemAction(
        name="submit",
        allowed_from=frozenset({"submitted"}),
        to_status="pending_approval",
        required_fields=(),
    ),
    "approve": SystemAction(
        name="approve",
        allowed_from=frozenset({"pending_approval"}),
        to_status="profile_created",
        required_fields=("hr_approver_id",),
    ),
    "create_profile": SystemAction(
        name="create_profile",
        allowed_from=frozenset({"profile_created"}),
        to_status="provisioning",
        required_fields=("employee_id",),
    ),
    "activate": SystemAction(
        name="activate",
        allowed_from=frozenset({"provisioning"}),
        to_status="active",
        required_fields=(),
    ),
    "complete": SystemAction(
        name="complete",
        allowed_from=frozenset({"active"}),
        to_status="completed",
        required_fields=("checklist_passed",),
    ),
}


class HrSystem(BaseSystem):
    def __init__(self, repo: "HrRepository | None" = None) -> None:
        if repo is None:
            from storage.systems_repository import HrRepository

            repo = HrRepository(Path("storage/systems.db"))
            repo.apply_migrations()
        self._repo = repo
        self._events: list[dict[str, Any]] = []

    @property
    def system_key(self) -> str:
        return "hr"

    @property
    def entity_type(self) -> str:
        return "hr_onboarding"

    @property
    def id_prefix(self) -> str:
        return "ONB-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return HR_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "completed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return HR_ACTIONS

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
                "error": {
                    "code": "entity_not_found",
                    "message": f"Onboarding {entity_id} not found",
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
        if action == "create_profile":
            update_data["employee_id"] = payload.get("employee_id")
        elif action == "provision":
            update_data["accounts"] = payload.get("accounts", [])
            update_data["devices"] = payload.get("devices", [])

        updated = self._repo.update(entity_id, update_data)
        self._add_event(entity_id, action, payload, now)

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
