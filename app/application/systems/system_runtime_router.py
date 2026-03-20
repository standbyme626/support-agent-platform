from __future__ import annotations

from typing import Any

from app.domain.systems import SystemRegistry, SystemResult


class SystemRuntimeRouter:
    def __init__(self, registry: SystemRegistry) -> None:
        self._registry = registry

    def route_create(
        self,
        system_key: str,
        payload: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        system = self._registry.get(system_key)
        if system is None:
            return SystemResult.failure(
                system=system_key,
                entity_type="unknown",
                entity_id=None,
                status="error",
                error_code="entity_not_found",
                error_message=f"System {system_key} not found",
                trace_id=trace_id,
            ).as_dict()

        return system.create(payload)

    def route_get(
        self,
        system_key: str,
        entity_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        system = self._registry.get(system_key)
        if system is None:
            return SystemResult.failure(
                system=system_key,
                entity_type="unknown",
                entity_id=entity_id,
                status="error",
                error_code="entity_not_found",
                error_message=f"System {system_key} not found",
                trace_id=trace_id,
            ).as_dict()

        entity = system.get(entity_id)
        if entity is None:
            return SystemResult.failure(
                system=system_key,
                entity_type=system.entity_type,
                entity_id=entity_id,
                status="error",
                error_code="entity_not_found",
                error_message=f"{system.entity_type} {entity_id} not found",
                trace_id=trace_id,
            ).as_dict()

        return SystemResult.success(
            system=system_key,
            entity_type=system.entity_type,
            entity_id=entity_id,
            status=str(entity.get("status", "")),
            summary=entity.get("summary"),
            data=entity,
            trace_id=trace_id,
        ).as_dict()

    def route_list(
        self,
        system_key: str,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        system = self._registry.get(system_key)
        if system is None:
            return SystemResult.failure(
                system=system_key,
                entity_type="unknown",
                entity_id=None,
                status="error",
                error_code="entity_not_found",
                error_message=f"System {system_key} not found",
                trace_id=trace_id or "",
            ).as_dict()

        return system.list(filters, page, page_size)

    def route_action(
        self,
        system_key: str,
        entity_id: str,
        action: str,
        operator_id: str,
        payload: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        system = self._registry.get(system_key)
        if system is None:
            return SystemResult.failure(
                system=system_key,
                entity_type="unknown",
                entity_id=entity_id,
                status="error",
                error_code="entity_not_found",
                error_message=f"System {system_key} not found",
                trace_id=trace_id,
            ).as_dict()

        return system.execute_action(entity_id, action, operator_id, payload, trace_id)

    def route_summary(self, trace_id: str) -> dict[str, Any]:
        systems = []
        for system_key in self._registry.list_systems():
            system = self._registry.get(system_key)
            if system:
                try:
                    items, total = system.list(None, 1, 1)
                    systems.append(
                        {
                            "system": system_key,
                            "entity_type": system.entity_type,
                            "id_prefix": system.id_prefix,
                            "lifecycle": list(system.lifecycle),
                            "total_entities": total,
                            "actions": list(system.actions.keys())
                            if hasattr(system, "actions")
                            else [],
                        }
                    )
                except Exception:
                    systems.append(
                        {
                            "system": system_key,
                            "entity_type": system.entity_type,
                            "id_prefix": system.id_prefix,
                            "lifecycle": list(system.lifecycle),
                            "total_entities": 0,
                            "actions": [],
                            "error": "failed to load",
                        }
                    )

        return {
            "ok": True,
            "total_systems": len(systems),
            "systems": systems,
            "trace_id": trace_id,
        }
