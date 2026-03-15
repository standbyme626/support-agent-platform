from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, TypedDict


class RuntimeTraceEntry(TypedDict, total=False):
    node: str
    event: str
    actor_id: str
    timestamp: str
    detail: dict[str, Any]


class RuntimeState(TypedDict):
    ticket: dict[str, Any]
    session: dict[str, Any]
    handoff: dict[str, Any]
    approval: dict[str, Any]
    grounding: dict[str, Any]
    trace: list[RuntimeTraceEntry]
    copilot_outputs: dict[str, Any]
    channel_route: dict[str, Any]
    runtime: dict[str, Any]


def build_initial_runtime_state(
    *,
    ticket_id: str,
    session_id: str,
    message_text: str,
    actor_id: str,
) -> RuntimeState:
    state: RuntimeState = {
        "ticket": {
            "ticket_id": ticket_id,
            "status": "received",
            "latest_message": message_text,
            "priority": "P3",
        },
        "session": {
            "session_id": session_id,
            "actor_id": actor_id,
            "ended": False,
        },
        "handoff": {
            "state": "none",
            "required": False,
        },
        "approval": {
            "approval_id": f"apr-{ticket_id}",
            "required": True,
            "status": "not_requested",
            "decision": None,
            "decided_by": None,
        },
        "grounding": {
            "sources": [],
            "strategy": "hybrid",
        },
        "trace": [],
        "copilot_outputs": {
            "ticket": None,
            "operator": None,
            "dispatch": None,
        },
        "channel_route": {
            "inbound": "wecom",
            "collab_target": None,
            "dispatch_decision": None,
            "delivery_status": "not_dispatched",
        },
        "runtime": {
            "graph": "u5-runtime-scaffold",
            "current_node": "start",
            "interrupted": False,
            "checkpoint_id": None,
            "created_at": _now_iso(),
        },
    }
    append_trace_entry(
        state,
        node="start",
        event="runtime_initialized",
        actor_id=actor_id,
        detail={"ticket_id": ticket_id, "session_id": session_id},
    )
    return state


def append_trace_entry(
    state: RuntimeState,
    *,
    node: str,
    event: str,
    actor_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    entry: RuntimeTraceEntry = {
        "node": node,
        "event": event,
        "timestamp": _now_iso(),
    }
    if actor_id:
        entry["actor_id"] = actor_id
    if detail:
        entry["detail"] = detail
    state["trace"].append(entry)


def clone_runtime_state(state: RuntimeState) -> RuntimeState:
    return json.loads(json.dumps(state))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
