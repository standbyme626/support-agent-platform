from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class ErrorResponse(BaseModel):
    ok: bool = False
    error: dict[str, Any]


api_router = APIRouter(prefix="/api", tags=["API"])


@api_router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


@api_router.get("/systems")
def list_systems() -> dict[str, Any]:
    from app.domain.systems import SystemKey

    return {
        "ok": True,
        "systems": SystemKey.all(),
    }
