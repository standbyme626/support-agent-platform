from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from core.trace_logger import new_trace_id


def run_session_new_issue(
    runtime: Any,
    *,
    session_id: str,
    payload: dict[str, Any],
    session_payload_getter: Callable[[Any, str], dict[str, Any] | None],
) -> dict[str, Any]:
    if runtime.gateway.bindings.session_mapper.get(session_id) is None:
        raise KeyError(f"session {session_id} not found")
    actor_id = str(payload.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")
    reason = str(payload.get("reason") or "new_issue_requested").strip() or "new_issue_requested"
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()
    runtime.gateway.bindings.session_mapper.begin_new_issue(
        session_id,
        metadata={
            "session_mode": "awaiting_new_issue",
            "last_intent": "new_issue_requested",
            "updated_by": actor_id,
            "new_issue_reason": reason,
        },
    )
    runtime.trace_logger.log(
        "session_new_issue",
        {
            "session_id": session_id,
            "actor_id": actor_id,
            "reason": reason,
            "event_type": "session_new_issue",
        },
        trace_id=trace_id,
        session_id=session_id,
    )
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "reason": reason,
        "event_type": "session_new_issue",
        "message": "Session switched to new issue mode.",
        "trace_id": trace_id,
        "session": session_payload_getter(runtime, session_id),
    }


def run_session_end_v2(
    runtime: Any,
    *,
    session_id: str,
    payload: dict[str, Any],
    session_payload_getter: Callable[[Any, str], dict[str, Any] | None],
) -> dict[str, Any]:
    if runtime.gateway.bindings.session_mapper.get(session_id) is None:
        raise KeyError(f"session {session_id} not found")
    actor_id = str(payload.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")
    reason = str(payload.get("reason") or "manual_end").strip() or "manual_end"
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()
    action_result = runtime.ticket_api_v2.end_session(
        session_id,
        actor_id=actor_id,
        reason=reason,
    )
    runtime.trace_logger.log(
        "session_end_v2",
        {
            "session_id": session_id,
            "actor_id": actor_id,
            "reason": reason,
            "event_type": action_result.event_type,
        },
        trace_id=trace_id,
        session_id=session_id,
    )
    return {
        **asdict(action_result),
        "trace_id": trace_id,
        "session": session_payload_getter(runtime, session_id),
    }
