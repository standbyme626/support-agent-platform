from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.erpnext_client import ERPNextClient
from app.domain.systems.base import SystemAction

if TYPE_CHECKING:
    from app.domain.systems.adapters.config import ERPNextConfig

SUPPLY_CHAIN_LIFECYCLE = (
    "awaiting_receipt",
    "received",
    "stocked",
    "allocated",
    "fulfilled",
    "returned",
    "closed",
)

SUPPLY_CHAIN_ACTIONS = {
    "receive": SystemAction(
        name="receive",
        allowed_from=frozenset({"awaiting_receipt"}),
        to_status="received",
        required_fields=("receipt_qty",),
    ),
    "stock": SystemAction(
        name="stock",
        allowed_from=frozenset({"received"}),
        to_status="stocked",
        required_fields=("location",),
    ),
    "allocate": SystemAction(
        name="allocate",
        allowed_from=frozenset({"stocked"}),
        to_status="allocated",
        required_fields=("order_id",),
    ),
    "fulfill": SystemAction(
        name="fulfill",
        allowed_from=frozenset({"allocated"}),
        to_status="fulfilled",
        required_fields=("shipment_id",),
    ),
    "return": SystemAction(
        name="return",
        allowed_from=frozenset({"fulfilled"}),
        to_status="returned",
        required_fields=("return_reason",),
    ),
    "close": SystemAction(
        name="close",
        allowed_from=frozenset({"fulfilled", "returned"}),
        to_status="closed",
        required_fields=(),
    ),
}


class ERPNextSupplyChainAdapter(ERPNextAdapter):
    def __init__(
        self,
        client: ERPNextClient | None = None,
        config: "ERPNextConfig | None" = None,
    ):
        super().__init__(client, config)

    @property
    def doctype(self) -> str:
        return "Stock Entry"

    @property
    def system_key(self) -> str:
        return "supply_chain"

    @property
    def entity_type(self) -> str:
        return "supply_chain_order"

    @property
    def id_prefix(self) -> str:
        return "SC-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return SUPPLY_CHAIN_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "closed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return SUPPLY_CHAIN_ACTIONS

    def _to_local_format(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": doc.get("name"),
            "status": doc.get("custom_status", "awaiting_receipt"),
            "order_type": doc.get("stock_entry_type"),
            "supplier_id": doc.get("custom_supplier_id"),
            "items_json": json.dumps(doc.get("items", [])),
            "total_amount": doc.get("total_amount"),
            "expected_delivery": doc.get("custom_expected_delivery"),
            "received_at": doc.get("custom_received_at"),
            "notes": doc.get("remarks"),
            "warehouse": doc.get("custom_warehouse"),
            "batch_no": doc.get("custom_batch_no"),
            "shipment_no": doc.get("custom_shipment_no"),
            "created_at": doc.get("creation"),
            "updated_at": doc.get("modified"),
        }

    def _to_erpnext_format(self, data: dict[str, Any]) -> dict[str, Any]:
        items_data = data.get("items_json", [])
        if isinstance(items_data, str):
            try:
                items_data = json.loads(items_data)
            except json.JSONDecodeError:
                items_data = []
        if not items_data:
            items_data = [
                {
                    "item_code": "STOCK_ITEM_2",
                    "qty": data.get("quantity") or 1,
                    "s_warehouse": "Stores - TC",
                    "t_warehouse": data.get("warehouse") or "Default Warehouse - TC",
                    "allow_zero_valuation_rate": 1,
                }
            ]
        return {
            "doctype": self.doctype,
            "company": "Test Company",
            "stock_entry_type": data.get("order_type") or "Material Receipt",
            "custom_supplier_id": data.get("supplier_id"),
            "items": items_data,
            "total_amount": data.get("total_amount"),
            "custom_expected_delivery": data.get("expected_delivery"),
            "custom_received_at": data.get("received_at"),
            "remarks": data.get("notes"),
            "custom_warehouse": data.get("warehouse") or "Stores - TC",
            "custom_batch_no": data.get("batch_no"),
            "custom_shipment_no": data.get("shipment_no"),
        }

    def _local_status_to_erpnext(self, local_status: str) -> dict[str, Any]:
        status_map = {
            "awaiting_receipt": {"custom_status": "awaiting_receipt", "docstatus": 0},
            "received": {"custom_status": "received", "docstatus": 1},
            "stocked": {"custom_status": "stocked", "docstatus": 1},
            "allocated": {"custom_status": "allocated", "docstatus": 1},
            "fulfilled": {"custom_status": "fulfilled", "docstatus": 1},
            "returned": {"custom_status": "returned", "docstatus": 1},
            "closed": {"custom_status": "closed", "docstatus": 2},
        }
        return status_map.get(local_status, {})

    def _erpnext_status_to_local(self, doc: dict[str, Any]) -> str:
        return doc.get("custom_status", "awaiting_receipt")
