from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.systems.base import BaseSystem, SystemAction

if TYPE_CHECKING:
    from storage.systems_repository import ProjectRepository


PROJECT_LIFECYCLE = (
    "requested",
    "planning",
    "active",
    "on_hold",
    "completed",
    "cancelled",
)

PROJECT_ACTIONS = {
    "plan": SystemAction(
        name="plan",
        allowed_from=frozenset({"requested"}),
        to_status="planning",
        required_fields=("project_name", "scope"),
    ),
    "activate": SystemAction(
        name="activate",
        allowed_from=frozenset({"planning"}),
        to_status="active",
        required_fields=(),
    ),
    "hold": SystemAction(
        name="hold",
        allowed_from=frozenset({"active"}),
        to_status="on_hold",
        required_fields=("hold_reason",),
    ),
    "resume": SystemAction(
        name="resume",
        allowed_from=frozenset({"on_hold"}),
        to_status="active",
        required_fields=(),
    ),
    "complete": SystemAction(
        name="complete",
        allowed_from=frozenset({"active"}),
        to_status="completed",
        required_fields=("completion_summary",),
    ),
    "cancel": SystemAction(
        name="cancel",
        allowed_from=frozenset({"requested", "planning", "active", "on_hold"}),
        to_status="cancelled",
        required_fields=("cancel_reason",),
    ),
}


class ProjectSystem(BaseSystem):
    def __init__(self, repo: "ProjectRepository | None" = None) -> None:
        if repo is None:
            from storage.systems_repository import ProjectRepository

            repo = ProjectRepository(Path("storage/systems.db"))
            repo.apply_migrations()
        self._repo = repo

    @property
    def system_key(self) -> str:
        return "project"

    @property
    def entity_type(self) -> str:
        return "project"

    @property
    def id_prefix(self) -> str:
        return "PRJ-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return PROJECT_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "completed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return PROJECT_ACTIONS

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
                "error": {"code": "entity_not_found", "message": f"Project {entity_id} not found"},
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

        updated = self._repo.update(entity_id, {"status": next_status})

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
