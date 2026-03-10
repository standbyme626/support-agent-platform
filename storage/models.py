from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

TicketPriority = Literal["P1", "P2", "P3", "P4"]
TicketStatus = Literal["open", "pending", "escalated", "handoff", "resolved", "closed"]
LifecycleStage = Literal[
    "intake",
    "classified",
    "retrieved",
    "drafted",
    "awaiting_human",
    "resolved",
    "closed",
]


@dataclass(frozen=True)
class SessionBinding:
    session_id: str
    thread_id: str
    ticket_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass(frozen=True)
class InboundEnvelope:
    channel: str
    session_id: str
    message_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundEnvelope:
    channel: str
    session_id: str
    body: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    channel: str
    session_id: str
    thread_id: str
    customer_id: str | None
    title: str
    latest_message: str
    intent: str
    priority: TicketPriority
    status: TicketStatus
    queue: str
    assignee: str | None
    needs_handoff: bool
    inbox: str = "default"
    lifecycle_stage: LifecycleStage = "intake"
    first_response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    escalated_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    resolution_note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class TicketEvent:
    event_id: str
    ticket_id: str
    event_type: str
    actor_type: str
    actor_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class KBDocument:
    doc_id: str
    source_type: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    ticket_id: str | None
    session_id: str
    route_decision: str
    retrieved_docs: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    summary: str = ""
    handoff_reason: str | None = None
