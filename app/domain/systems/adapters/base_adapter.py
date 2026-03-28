from __future__ import annotations

from abc import ABC
from datetime import UTC, datetime
from typing import Any

from app.domain.systems.adapters.config import ERPNextConfig
from app.domain.systems.adapters.erpnext_client import ERPNextClient, get_shared_client
from app.domain.systems.base import BaseSystem


class ERPNextAdapter(BaseSystem, ABC):
    def __init__(
        self,
        client: ERPNextClient | None = None,
        config: ERPNextConfig | None = None,
    ):
        self._client = client or get_shared_client(config)

    @property
    def doctype(self) -> str:
        raise NotImplementedError("Subclass must define doctype")

    @property
    def system_key(self) -> str:
        raise NotImplementedError("Subclass must define system_key")

    @property
    def entity_type(self) -> str:
        raise NotImplementedError("Subclass must define entity_type")

    @property
    def id_prefix(self) -> str:
        raise NotImplementedError("Subclass must define id_prefix")

    @property
    def terminal_status(self) -> str:
        raise NotImplementedError("Subclass must define terminal_status")

    def _to_local_format(self, doc: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Subclass must implement _to_local_format")

    def _to_erpnext_format(self, data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Subclass must implement _to_erpnext_format")

    def _local_status_to_erpnext(self, local_status: str) -> dict[str, Any]:
        raise NotImplementedError("Subclass must implement _local_status_to_erpnext")

    def _erpnext_status_to_local(self, doc: dict[str, Any]) -> str:
        raise NotImplementedError("Subclass must implement _erpnext_status_to_local")

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        erpnext_data = self._to_erpnext_format(payload)
        doc = self._client.insert(self.doctype, erpnext_data)
        entity = self._to_local_format(doc)
        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "entity_id": entity.get("id", doc.get("name")),
            "status": entity.get("status", "draft"),
            "created_at": now,
            "updated_at": now,
            "data": entity,
        }

    def get(self, entity_id: str) -> dict[str, Any] | None:
        doc = self._client.get_doc(self.doctype, entity_id)
        if doc is None:
            return None
        return self._to_local_format(doc)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        result = self._client.list(
            self.doctype,
            filters=filters,
            page=page,
            page_length=page_size,
        )
        items = [self._to_local_format(doc) for doc in result.get("data", [])]
        return {
            "ok": True,
            "system": self.system_key,
            "entity_type": self.entity_type,
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": result.get("total", len(items)),
            },
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
        doc = self._client.get_doc(self.doctype, entity_id)

        if doc is None:
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": "error",
                "error": {"code": "entity_not_found", "message": f"Entity {entity_id} not found"},
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
                "status": doc.get("status"),
                "error": {"code": "forbidden_action", "message": f"Unknown action: {action}"},
                "updated_at": now,
                "trace_id": trace_id,
            }

        if not self.validate_transition(doc.get("status", ""), action):
            return {
                "ok": False,
                "system": self.system_key,
                "entity_type": self.entity_type,
                "entity_id": entity_id,
                "status": doc.get("status"),
                "error": {
                    "code": "invalid_state_transition",
                    "message": f"Cannot {action} from status {doc.get('status')}",
                    "details": {"allowed_from": list(self.actions[action].allowed_from)},
                },
                "updated_at": now,
                "trace_id": trace_id,
            }

        update_data = self._local_status_to_erpnext(next_status)
        if payload:
            update_data.update(payload)

        updated_doc = self._client.update(self.doctype, entity_id, update_data)
        entity = self._to_local_format(updated_doc)

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
