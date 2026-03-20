from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.application.systems import SystemIntentRouter, SystemRuntimeRouter
from app.domain.systems import SystemRegistry, SystemResult


class CreateRequest(BaseModel):
    trace_id: str | None = None


class ActionRequest(BaseModel):
    operator_id: str = "system"
    trace_id: str | None = None


class RouteRequest(BaseModel):
    text: str


class RouteResponse(BaseModel):
    ok: bool = True
    system: str
    confidence: float
    fields: dict[str, Any]


def create_router(registry: SystemRegistry | None = None) -> APIRouter:
    if registry is None:
        registry = SystemRegistry()

    router = SystemRuntimeRouter(registry)
    intent_router = SystemIntentRouter()
    systems_router = APIRouter(prefix="/api/systems", tags=["Systems"])

    @systems_router.post("/{system}/create")
    def create_entity(
        system: str,
        body: CreateRequest,
    ) -> dict[str, Any]:
        trace_id = body.trace_id or str(uuid.uuid4())
        result = router.route_create(system, body.model_dump(exclude_none=True), trace_id)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @systems_router.get("/summary")
    def get_systems_summary() -> dict[str, Any]:
        trace_id = str(uuid.uuid4())
        return router.route_summary(trace_id)

    @systems_router.get("/{system}")
    def list_entities(
        system: str,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        trace_id = str(uuid.uuid4())
        return router.route_list(system, None, page, page_size, trace_id)

    @systems_router.post("/{system}/{entity_id}/{action}")
    def execute_action(
        system: str,
        entity_id: str,
        action: str,
        body: ActionRequest,
    ) -> dict[str, Any]:
        trace_id = body.trace_id or str(uuid.uuid4())
        payload = body.model_dump(exclude={"operator_id", "trace_id"})
        result = router.route_action(system, entity_id, action, body.operator_id, payload, trace_id)

        if not result.get("ok"):
            error_code = result.get("error", {}).get("code", "unknown")
            status_map = {
                "entity_not_found": 404,
                "invalid_state_transition": 409,
                "validation_error": 422,
            }
            raise HTTPException(status_code=status_map.get(error_code, 400), detail=result)

        return result

    intent_router_api = APIRouter(prefix="/api", tags=["Intent"])

    @intent_router_api.post("/route", response_model=RouteResponse)
    def route_intent(body: RouteRequest) -> RouteResponse:
        system = intent_router.route(body.text)
        system_key, confidence = intent_router.route_with_confidence(body.text)
        fields = intent_router.extract_fields(body.text, system)
        return RouteResponse(
            ok=True,
            system=system,
            confidence=confidence,
            fields=fields,
        )

    return systems_router, intent_router_api
