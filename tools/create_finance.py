from __future__ import annotations

from typing import Any

from app.domain.systems.adapters.erpnext_finance import ERPNextFinanceAdapter


def create_finance(payload: dict[str, Any]) -> dict[str, Any]:
    adapter = ERPNextFinanceAdapter()
    return adapter.create(payload)


def get_finance(entity_id: str) -> dict[str, Any] | None:
    adapter = ERPNextFinanceAdapter()
    return adapter.get(entity_id)


def list_finance(args: dict[str, Any] | None = None) -> dict[str, Any]:
    if args is None:
        args = {}
    adapter = ERPNextFinanceAdapter()
    return adapter.list(
        filters=args.get("filters"),
        page=args.get("page", 1),
        page_size=args.get("page_size", 20),
    )


def execute_finance_action(
    entity_id: str,
    action: str,
    operator_id: str,
    payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    adapter = ERPNextFinanceAdapter()
    return adapter.execute_action(entity_id, action, operator_id, payload, trace_id)
