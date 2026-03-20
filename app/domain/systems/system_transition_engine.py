from __future__ import annotations

from typing import Any

from app.domain.systems.base import BaseSystem
from app.domain.systems.system_errors import (
    ForbiddenActionError,
    InvalidStateTransitionError,
    ValidationError,
)


class SystemTransitionEngine:
    def __init__(self, system: BaseSystem) -> None:
        self._system = system

    def execute(
        self,
        entity_id: str,
        action: str,
        operator_id: str,
        payload: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        entity = self._system.get(entity_id)
        if entity is None:
            return self._error_result(
                "entity_not_found", f"{self._system.entity_type} not found", trace_id
            )

        current_status = str(entity.get("status", ""))
        if not self._system.validate_transition(current_status, action):
            allowed_from = self._get_allowed_from(action)
            return self._error_result(
                "invalid_state_transition",
                f"Cannot perform {action} from status {current_status}",
                trace_id,
                details={
                    "current_status": current_status,
                    "action": action,
                    "allowed_from": list(allowed_from),
                },
            )

        action_def = self._system.actions.get(action)
        if action_def is None:
            return self._error_result("forbidden_action", f"Unknown action: {action}", trace_id)

        missing_fields = self._check_required_fields(action_def.required_fields, payload)
        if missing_fields:
            return self._error_result(
                "validation_error",
                f"Missing required fields: {missing_fields}",
                trace_id,
                details={"missing_fields": missing_fields},
            )

        return self._system.execute_action(entity_id, action, operator_id, payload, trace_id)

    def _get_allowed_from(self, action: str) -> frozenset[str]:
        action_def = self._system.actions.get(action)
        if action_def is None:
            return frozenset()
        return action_def.allowed_from

    def _check_required_fields(
        self,
        required_fields: tuple[str, ...],
        payload: dict[str, Any],
    ) -> list[str]:
        missing = []
        for field in required_fields:
            if field not in payload or payload[field] is None:
                missing.append(field)
        return missing

    def _error_result(
        self,
        code: str,
        message: str,
        trace_id: str,
        details: dict | None = None,
    ) -> dict[str, Any]:
        from app.domain.systems.system_result import SystemResult

        return SystemResult.failure(
            system=self._system.system_key,
            entity_type=self._system.entity_type,
            entity_id=None,
            status="error",
            error_code=code,
            error_message=message,
            details=details,
            trace_id=trace_id,
        ).as_dict()
