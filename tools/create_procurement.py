from __future__ import annotations

from typing import Any

from app.domain.systems.adapters.erpnext_procurement import ERPNextProcurementAdapter


def create_procurement(payload: dict[str, Any]) -> dict[str, Any]:
    adapter = ERPNextProcurementAdapter()
    return adapter.create(payload)


def get_procurement(entity_id: str) -> dict[str, Any] | None:
    adapter = ERPNextProcurementAdapter()
    return adapter.get(entity_id)


def list_procurement(args: dict[str, Any] | None = None) -> dict[str, Any]:
    if args is None:
        args = {}
    adapter = ERPNextProcurementAdapter()
    return adapter.list(
        filters=args.get("filters"),
        page=args.get("page", 1),
        page_size=args.get("page_size", 20),
    )


def execute_procurement_action(
    entity_id: str,
    action: str,
    operator_id: str,
    payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    adapter = ERPNextProcurementAdapter()
    return adapter.execute_action(entity_id, action, operator_id, payload, trace_id)
