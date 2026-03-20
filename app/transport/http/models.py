from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SystemResultResponse(BaseModel):
    ok: bool
    system: str
    entity_type: str
    entity_id: str | None = None
    status: str
    summary: str | None = None
    next_action: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None
    trace_id: str | None = None


class ErrorResponse(BaseModel):
    ok: bool = False
    error: dict[str, Any]


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class TicketCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    channel: str = Field(default="api")
    priority: str | None = None
    category: str | None = None
    requester_id: str | None = None


class TicketActionRequest(BaseModel):
    operator_id: str | None = None
    comment: str | None = None
    trace_id: str | None = None


class IntakeRunRequest(BaseModel):
    channel: str = Field(default="api")
    session_id: str
    message_text: str = Field(..., min_length=1)
    operator_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionResetRequest(BaseModel):
    operator_id: str | None = None


class SessionNewIssueRequest(BaseModel):
    message_text: str = Field(..., min_length=1)
    operator_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemCreateRequest(BaseModel):
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemActionRequest(BaseModel):
    operator_id: str = Field(default="system")
    trace_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class IntentRouteRequest(BaseModel):
    text: str = Field(..., min_length=1)


class IntentRouteResponse(BaseModel):
    ok: bool = True
    system: str
    confidence: float
    fields: dict[str, Any]
