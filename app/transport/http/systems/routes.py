from __future__ import annotations

import uuid
from typing import Any

from app.application.systems import SystemRuntimeRouter, SystemIntentRouter
from app.domain.systems import SystemRegistry, SystemResult


def create_systems_routes(registry: SystemRegistry) -> dict[str, Any]:
    router = SystemRuntimeRouter(registry)
    intent_router = SystemIntentRouter()

    routes = {}

    for method, path_template, handler in [
        ("POST", "/api/{system}/create", _handle_create),
        ("GET", "/api/{system}/{entity_id}", _handle_get),
        ("GET", "/api/{system}", _handle_list),
        ("POST", "/api/{system}/{entity_id}/{action}", _handle_action),
        ("POST", "/api/route", _handle_route),
    ]:
        route_key = f"{method} {path_template}"
        routes[route_key] = {
            "method": method,
            "path_template": path_template,
            "handler": handler,
            "router": router,
            "intent_router": intent_router,
        }

    return routes


def _handle_create(
    system_key: str,
    body: dict[str, Any],
    router: SystemRuntimeRouter,
    intent_router: SystemIntentRouter,
) -> tuple[int, dict[str, Any]]:
    trace_id = body.get("trace_id") or str(uuid.uuid4())
    result = router.route_create(system_key, body, trace_id)
    status_code = 201 if result.get("ok") else 400
    return status_code, result


def _handle_get(
    system_key: str,
    entity_id: str,
    router: SystemRuntimeRouter,
) -> tuple[int, dict[str, Any]]:
    trace_id = str(uuid.uuid4())
    result = router.route_get(system_key, entity_id, trace_id)
    status_code = 200 if result.get("ok") else 404
    return status_code, result


def _handle_list(
    system_key: str,
    query_params: dict[str, Any],
    router: SystemRuntimeRouter,
) -> tuple[int, dict[str, Any]]:
    trace_id = query_params.get("trace_id") or str(uuid.uuid4())
    page = int(query_params.get("page", 1))
    page_size = int(query_params.get("page_size", 20))
    result = router.route_list(system_key, query_params, page, page_size, trace_id)
    return 200, result


def _handle_action(
    system_key: str,
    entity_id: str,
    action: str,
    body: dict[str, Any],
    router: SystemRuntimeRouter,
) -> tuple[int, dict[str, Any]]:
    trace_id = body.get("trace_id") or str(uuid.uuid4())
    operator_id = body.get("operator_id", "system")
    payload = {k: v for k, v in body.items() if k not in ("trace_id", "operator_id")}
    result = router.route_action(system_key, entity_id, action, operator_id, payload, trace_id)

    if not result.get("ok"):
        error_code = result.get("error", {}).get("code", "unknown")
        status_map = {
            "entity_not_found": 404,
            "invalid_state_transition": 409,
            "validation_error": 422,
        }
        status_code = status_map.get(error_code, 400)
    else:
        status_code = 200

    return status_code, result


def _handle_route(
    body: dict[str, Any],
    intent_router: SystemIntentRouter,
) -> tuple[int, dict[str, Any]]:
    text = body.get("text", "")
    system_key = intent_router.route(text)
    system_key_confidence, confidence = intent_router.route_with_confidence(text)
    fields = intent_router.extract_fields(text, system_key)

    return 200, {
        "ok": True,
        "system": system_key,
        "confidence": confidence,
        "fields": fields,
    }
