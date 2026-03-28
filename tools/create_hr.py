from __future__ import annotations

from typing import Any

from app.domain.systems.adapters.erpnext_hr import ERPNextHrAdapter


def create_hr(payload: dict[str, Any]) -> dict[str, Any]:
    adapter = ERPNextHrAdapter()
    return adapter.create(payload)


def get_hr(entity_id: str) -> dict[str, Any] | None:
    adapter = ERPNextHrAdapter()
    return adapter.get(entity_id)


def list_hr(args: dict[str, Any] | None = None) -> dict[str, Any]:
    if args is None:
        args = {}
    adapter = ERPNextHrAdapter()
    return adapter.list(
        filters=args.get("filters"),
        page=args.get("page", 1),
        page_size=args.get("page_size", 20),
    )


def execute_hr_action(
    entity_id: str,
    action: str,
    operator_id: str,
    payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    adapter = ERPNextHrAdapter()
    return adapter.execute_action(entity_id, action, operator_id, payload, trace_id)
