from __future__ import annotations

from typing import Any

from app.domain.systems.adapters.erpnext_supply_chain import ERPNextSupplyChainAdapter


def create_supply_chain(payload: dict[str, Any]) -> dict[str, Any]:
    adapter = ERPNextSupplyChainAdapter()
    return adapter.create(payload)


def get_supply_chain(entity_id: str) -> dict[str, Any] | None:
    adapter = ERPNextSupplyChainAdapter()
    return adapter.get(entity_id)


def list_supply_chain(
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    adapter = ERPNextSupplyChainAdapter()
    return adapter.list(filters=filters, page=page, page_size=page_size)


def execute_supply_chain_action(
    entity_id: str,
    action: str,
    operator_id: str,
    payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    adapter = ERPNextSupplyChainAdapter()
    return adapter.execute_action(entity_id, action, operator_id, payload, trace_id)
