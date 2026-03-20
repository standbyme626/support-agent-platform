from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SystemResult:
    ok: bool
    system: str
    entity_type: str
    entity_id: str | None
    status: str
    summary: str | None = None
    next_action: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None
    trace_id: str | None = None

    @staticmethod
    def success(
        system: str,
        entity_type: str,
        entity_id: str | None,
        status: str,
        summary: str | None = None,
        next_action: str | None = None,
        data: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> SystemResult:
        return SystemResult(
            ok=True,
            system=system,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            summary=summary,
            next_action=next_action,
            data=data or {},
            created_at=_now_iso(),
            updated_at=_now_iso(),
            trace_id=trace_id,
        )

    @staticmethod
    def failure(
        system: str,
        entity_type: str,
        entity_id: str | None,
        status: str,
        error_code: str,
        error_message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> SystemResult:
        return SystemResult(
            ok=False,
            system=system,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            error={
                "code": error_code,
                "message": error_message,
                "retryable": retryable,
                "details": details or {},
            },
            trace_id=trace_id,
            updated_at=_now_iso(),
        )

    def as_dict(self) -> dict[str, Any]:
        result = {
            "ok": self.ok,
            "system": self.system,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "status": self.status,
        }
        if self.summary is not None:
            result["summary"] = self.summary
        if self.next_action is not None:
            result["next_action"] = self.next_action
        if self.data:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        if self.created_at is not None:
            result["created_at"] = self.created_at
        if self.updated_at is not None:
            result["updated_at"] = self.updated_at
        if self.trace_id is not None:
            result["trace_id"] = self.trace_id
        return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
