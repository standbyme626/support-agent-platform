from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.systems.base import BaseSystem, SystemAction

if TYPE_CHECKING:
    from storage.systems_repository import KbRepository


KB_LIFECYCLE = (
    "draft",
    "review",
    "published",
    "expiring",
    "archived",
)

KB_ACTIONS = {
    "submit_review": SystemAction(
        name="submit_review",
        allowed_from=frozenset({"draft"}),
        to_status="review",
        required_fields=(),
    ),
    "publish": SystemAction(
        name="publish",
        allowed_from=frozenset({"review"}),
        to_status="published",
        required_fields=(),
    ),
    "reject": SystemAction(
        name="reject",
        allowed_from=frozenset({"review"}),
        to_status="draft",
        required_fields=("reject_reason",),
    ),
    "expire": SystemAction(
        name="expire",
        allowed_from=frozenset({"published"}),
        to_status="expiring",
        required_fields=(),
    ),
    "archive": SystemAction(
        name="archive",
        allowed_from=frozenset({"published", "expiring"}),
        to_status="archived",
        required_fields=("archive_reason",),
    ),
    "update": SystemAction(
        name="update",
        allowed_from=frozenset({"published"}),
        to_status="published",
        required_fields=("content",),
    ),
}


class KbSystem(BaseSystem):
    def __init__(self, repo: "KbRepository | None" = None) -> None:
        if repo is None:
            from storage.systems_repository import KbRepository

            repo = KbRepository(Path("storage/systems.db"))
            repo.apply_migrations()
        self._repo = repo

    @property
    def system_key(self) -> str:
        return "kb"

    @property
    def entity_type(self) -> str:
        return "kb_article"

    @property
    def id_prefix(self) -> str:
        return "KB-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return KB_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "archived"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return KB_ACTIONS

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
                "error": {"code": "entity_not_found", "message": f"Article {entity_id} not found"},
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
        if action == "publish":
            update_data["published_at"] = now
        elif action == "update":
            update_data["version"] = entity.get("version", 1) + 1

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
