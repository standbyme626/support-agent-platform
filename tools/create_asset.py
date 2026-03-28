from __future__ import annotations

from typing import Any

from app.domain.systems.adapters.erpnext_asset import ERPNextAssetAdapter


def create_asset(payload: dict[str, Any]) -> dict[str, Any]:
    adapter = ERPNextAssetAdapter()
    return adapter.create(payload)


def get_asset(entity_id: str) -> dict[str, Any] | None:
    adapter = ERPNextAssetAdapter()
    return adapter.get(entity_id)


def list_asset(
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    adapter = ERPNextAssetAdapter()
    return adapter.list(filters=filters, page=page, page_size=page_size)


def execute_asset_action(
    entity_id: str,
    action: str,
    operator_id: str,
    payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    adapter = ERPNextAssetAdapter()
    return adapter.execute_action(entity_id, action, operator_id, payload, trace_id)
