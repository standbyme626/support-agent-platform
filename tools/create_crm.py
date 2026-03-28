from __future__ import annotations

from typing import Any

from app.domain.systems.adapters.erpnext_crm import ERPNextCrmAdapter


def create_crm(payload: dict[str, Any]) -> dict[str, Any]:
    adapter = ERPNextCrmAdapter()
    return adapter.create(payload)


def get_crm(entity_id: str) -> dict[str, Any] | None:
    adapter = ERPNextCrmAdapter()
    return adapter.get(entity_id)


def list_crm(args: dict[str, Any] | None = None) -> dict[str, Any]:
    if args is None:
        args = {}
    adapter = ERPNextCrmAdapter()
    return adapter.list(
        filters=args.get("filters"),
        page=args.get("page", 1),
        page_size=args.get("page_size", 20),
    )


def execute_crm_action(
    entity_id: str,
    action: str,
    operator_id: str,
    payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    adapter = ERPNextCrmAdapter()
    return adapter.execute_action(entity_id, action, operator_id, payload, trace_id)
