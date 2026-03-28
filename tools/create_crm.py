from __future__ import annotations

from typing import Any

from app.domain.systems.adapters.erpnext_crm import ERPNextCrmAdapter


def create_crm(payload: dict[str, Any]) -> dict[str, Any]:
    adapter = ERPNextCrmAdapter()
    return adapter.create(payload)


def get_crm(entity_id: str) -> dict[str, Any] | None:
    adapter = ERPNextCrmAdapter()
    return adapter.get(entity_id)


def list_crm(
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    adapter = ERPNextCrmAdapter()
    return adapter.list(filters=filters, page=page, page_size=page_size)


def execute_crm_action(
    entity_id: str,
    action: str,
    operator_id: str,
    payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    adapter = ERPNextCrmAdapter()
    return adapter.execute_action(entity_id, action, operator_id, payload, trace_id)
