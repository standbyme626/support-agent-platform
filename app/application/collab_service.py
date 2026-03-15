from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from app.graph_runtime.collab_graph import CollabGraphRuntime, build_collab_graph


class CollabService:
    """Collaboration application service backed by graph runtime."""

    _ACTION_ALIASES: ClassVar[dict[str, str]] = {"close": "customer_confirm"}

    def __init__(self, graph_runtime: CollabGraphRuntime | None = None) -> None:
        self._graph_runtime = graph_runtime or build_collab_graph()

    def run(self, ticket_id: str, message_text: str) -> dict[str, Any]:
        return self.prepare_action(
            ticket_id=ticket_id,
            action="claim",
            actor_id="collab-service",
            note=message_text,
            metadata={"source": "collab_service.run"},
        )

    def prepare_action(
        self,
        *,
        ticket_id: str,
        action: str,
        actor_id: str,
        note: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_action = self._normalize_action(action)
        state = self._graph_runtime.run(
            ticket_id=ticket_id,
            action=normalized_action,
            actor_id=actor_id,
            note=note,
            metadata=dict(metadata or {}),
        )
        result = dict(state)
        result["normalized_action"] = normalized_action
        return result

    def resume_action(
        self,
        *,
        checkpoint_id: str,
        decision: Literal["approve", "reject"],
        actor_id: str,
    ) -> dict[str, Any]:
        state = self._graph_runtime.resume(
            checkpoint_id=checkpoint_id,
            decision=decision,
            actor_id=actor_id,
        )
        return dict(state)

    @classmethod
    def _normalize_action(cls, action: str) -> str:
        raw = str(action or "").strip()
        if not raw:
            return raw
        raw = raw.replace("-", "_")
        return cls._ACTION_ALIASES.get(raw, raw)


def extract_action_note(payload: Mapping[str, Any]) -> str:
    for key in ("note", "resolution_note", "reason", "message_text", "query"):
        value = payload.get(key)
        if value is None:
            continue
        note = str(value).strip()
        if note:
            return note
    return ""


def prepare_collab_action_state(
    collab_service: CollabService,
    *,
    ticket_id: str,
    action: str,
    actor_id: str,
    payload: Mapping[str, Any],
    source: str = "ops_api",
) -> dict[str, Any] | None:
    try:
        return collab_service.prepare_action(
            ticket_id=ticket_id,
            action=action,
            actor_id=actor_id,
            note=extract_action_note(payload),
            metadata={
                "source": source,
                "trace_id": str(payload.get("trace_id") or "").strip() or None,
            },
        )
    except Exception as exc:
        return {
            "error": "collab_graph_prepare_failed",
            "message": str(exc),
            "action": action,
        }


def resume_collab_action_state_from_payload(
    collab_service: CollabService,
    *,
    pending_payload: Mapping[str, Any],
    decision: str,
    actor_id: str,
) -> dict[str, Any] | None:
    checkpoint_id = str(pending_payload.get("collab_checkpoint_id") or "").strip()
    if not checkpoint_id:
        return None
    try:
        return collab_service.resume_action(
            checkpoint_id=checkpoint_id,
            decision="approve" if decision == "approve" else "reject",
            actor_id=actor_id,
        )
    except Exception as exc:
        return {
            "error": "collab_graph_resume_failed",
            "message": str(exc),
            "checkpoint_id": checkpoint_id,
            "decision": decision,
        }
