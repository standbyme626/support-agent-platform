from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from storage.models import Ticket

HANDOFF_CONTEXT_KEY = "handoff_context"


def build_handoff_context(
    *,
    ticket: Ticket,
    summary: str,
    recommended_actions: Sequence[Mapping[str, Any]] | None = None,
    grounding_sources: Sequence[Mapping[str, Any]] | None = None,
    trace_events: Sequence[str] | None = None,
    llm_trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    action_titles: list[str] = []
    for item in recommended_actions or ():
        title = item.get("title") or item.get("action")
        if title:
            action_titles.append(str(title))

    source_ids: list[str] = []
    for item in grounding_sources or ():
        source_id = item.get("source_id") or item.get("doc_id")
        if source_id:
            source_ids.append(str(source_id))

    return {
        "ticket_id": ticket.ticket_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "intent": ticket.intent,
        "queue": ticket.queue,
        "priority": ticket.priority,
        "risk_level": ticket.risk_level,
        "status": ticket.status,
        "summary": summary[:300],
        "recommended_actions": action_titles[:5],
        "grounding_source_ids": source_ids[:5],
        "trace_events": list(trace_events or [])[:10],
        "llm_trace": dict(llm_trace or {}),
    }


def build_approval_context(
    *,
    ticket: Ticket,
    action_type: str,
    command_line: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = extract_handoff_context(ticket)
    context.update(
        {
            "requested_action": action_type,
            "resume_handoff_state": ticket.handoff_state,
            "command_line": command_line,
            "payload_preview": dict(payload or {}),
        }
    )
    return context


def extract_handoff_context(ticket: Ticket) -> dict[str, Any]:
    raw = ticket.metadata.get(HANDOFF_CONTEXT_KEY)
    if isinstance(raw, dict):
        return dict(raw)
    return {}
