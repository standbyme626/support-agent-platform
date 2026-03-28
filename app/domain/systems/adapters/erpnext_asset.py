from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.erpnext_client import ERPNextClient
from app.domain.systems.base import SystemAction

if TYPE_CHECKING:
    from app.domain.systems.adapters.config import ERPNextConfig

ASSET_LIFECYCLE = (
    "requested",
    "procurement",
    "inventory",
    "assigned",
    "maintenance",
    "retired",
    "disposed",
)

ASSET_ACTIONS = {
    "request": SystemAction(
        name="request",
        allowed_from=frozenset({"requested"}),
        to_status="procurement",
        required_fields=("asset_name", "asset_type"),
    ),
    "receive": SystemAction(
        name="receive",
        allowed_from=frozenset({"procurement"}),
        to_status="inventory",
        required_fields=("asset_tag",),
    ),
    "assign": SystemAction(
        name="assign",
        allowed_from=frozenset({"inventory"}),
        to_status="assigned",
        required_fields=("assigned_to",),
    ),
    "return_asset": SystemAction(
        name="return_asset",
        allowed_from=frozenset({"assigned"}),
        to_status="inventory",
        required_fields=(),
    ),
    "maintenance": SystemAction(
        name="maintenance",
        allowed_from=frozenset({"assigned", "inventory"}),
        to_status="maintenance",
        required_fields=("maintenance_reason",),
    ),
    "retire": SystemAction(
        name="retire",
        allowed_from=frozenset({"assigned", "inventory", "maintenance"}),
        to_status="retired",
        required_fields=("retirement_reason",),
    ),
    "dispose": SystemAction(
        name="dispose",
        allowed_from=frozenset({"retired"}),
        to_status="disposed",
        required_fields=("disposal_method",),
    ),
}


class ERPNextAssetAdapter(ERPNextAdapter):
    def __init__(
        self,
        client: ERPNextClient | None = None,
        config: "ERPNextConfig | None" = None,
    ):
        super().__init__(client, config)

    @property
    def doctype(self) -> str:
        return "Asset"

    @property
    def system_key(self) -> str:
        return "asset"

    @property
    def entity_type(self) -> str:
        return "asset"

    @property
    def id_prefix(self) -> str:
        return "ASSET-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return ASSET_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "disposed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return ASSET_ACTIONS

    def _to_local_format(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": doc.get("name"),
            "status": doc.get("custom_status", "inventory"),
            "asset_tag": doc.get("asset_tag"),
            "name": doc.get("asset_name"),
            "category": doc.get("asset_category"),
            "model": doc.get("model_number"),
            "serial_number": doc.get("serial_no"),
            "location": doc.get("location"),
            "assigned_to": doc.get("custodian"),
            "assigned_at": doc.get("custom_assigned_at"),
            "purchase_date": doc.get("purchase_date"),
            "warranty_expires": doc.get("warranty_expiry_date"),
            "value": doc.get("asset_value"),
            "supplier_id": doc.get("supplier"),
            "custodian": doc.get("custodian"),
            "depreciation": doc.get("depreciation_method"),
            "created_at": doc.get("creation"),
            "updated_at": doc.get("modified"),
        }

    def _to_erpnext_format(self, data: dict[str, Any]) -> dict[str, Any]:
        value = data.get("value") or 0
        from datetime import date

        today = date.today().isoformat()
        return {
            "doctype": self.doctype,
            "asset_name": data.get("name") or data.get("asset_name"),
            "asset_category": data.get("category") or "IT Equipment",
            "item_code": "FIXED_ASSET_ITEM",
            "asset_tag": data.get("asset_tag"),
            "model_number": data.get("model"),
            "serial_no": data.get("serial_number"),
            "location": data.get("location") or "Head Office",
            "custodian": data.get("assigned_to"),
            "purchase_date": data.get("purchase_date") or today,
            "warranty_expiry_date": data.get("warranty_expires"),
            "gross_purchase_amount": value,
            "net_purchase_amount": value,
            "asset_value": value,
            "company": "Test Company",
            "supplier": data.get("supplier_id") or "Default Supplier",
            "depreciation_method": data.get("depreciation") or "Straight Line",
        }

    def _local_status_to_erpnext(self, local_status: str) -> dict[str, Any]:
        status_map = {
            "requested": {"custom_status": "requested", "docstatus": 0},
            "procurement": {"custom_status": "procurement", "docstatus": 0},
            "inventory": {"custom_status": "inventory", "docstatus": 1},
            "assigned": {"custom_status": "assigned", "docstatus": 1},
            "maintenance": {"custom_status": "maintenance", "docstatus": 1},
            "retired": {"custom_status": "retired", "docstatus": 2},
            "disposed": {"custom_status": "disposed", "docstatus": 2},
        }
        return status_map.get(local_status, {})

    def _erpnext_status_to_local(self, doc: dict[str, Any]) -> str:
        return doc.get("custom_status", "inventory")
