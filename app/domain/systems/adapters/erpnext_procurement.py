from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.erpnext_client import ERPNextClient
from app.domain.systems.base import SystemAction

if TYPE_CHECKING:
    from app.domain.systems.adapters.config import ERPNextConfig

PROCUREMENT_LIFECYCLE = (
    "draft",
    "pending_approval",
    "approved",
    "ordered",
    "received",
    "invoiced",
    "completed",
)

PROCUREMENT_ACTIONS = {
    "submit": SystemAction(
        name="submit",
        allowed_from=frozenset({"draft"}),
        to_status="pending_approval",
        required_fields=(),
    ),
    "approve": SystemAction(
        name="approve",
        allowed_from=frozenset({"pending_approval"}),
        to_status="approved",
        required_fields=("approver_id",),
    ),
    "reject": SystemAction(
        name="reject",
        allowed_from=frozenset({"pending_approval"}),
        to_status="draft",
        required_fields=("reject_reason",),
    ),
    "order": SystemAction(
        name="order",
        allowed_from=frozenset({"approved"}),
        to_status="ordered",
        required_fields=("po_no", "supplier_id"),
    ),
    "receive": SystemAction(
        name="receive",
        allowed_from=frozenset({"ordered"}),
        to_status="received",
        required_fields=("received_qty",),
    ),
    "invoice": SystemAction(
        name="invoice",
        allowed_from=frozenset({"received"}),
        to_status="invoiced",
        required_fields=("invoice_ref",),
    ),
    "complete": SystemAction(
        name="complete",
        allowed_from=frozenset({"received", "invoiced"}),
        to_status="completed",
        required_fields=(),
    ),
}


class ERPNextProcurementAdapter(ERPNextAdapter):
    def __init__(
        self,
        client: ERPNextClient | None = None,
        config: "ERPNextConfig | None" = None,
    ):
        super().__init__(client, config)

    @property
    def doctype(self) -> str:
        return "Purchase Order"

    @property
    def system_key(self) -> str:
        return "procurement"

    @property
    def entity_type(self) -> str:
        return "procurement_request"

    @property
    def id_prefix(self) -> str:
        return "PR-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return PROCUREMENT_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "completed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return PROCUREMENT_ACTIONS

    def _to_local_format(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": doc.get("name"),
            "status": doc.get("custom_status", "draft"),
            "requester_id": doc.get("custom_requester_id"),
            "item_name": doc.get("custom_item_name"),
            "category": doc.get("custom_category"),
            "quantity": doc.get("custom_quantity"),
            "budget": doc.get("custom_budget"),
            "business_reason": doc.get("custom_business_reason"),
            "urgency": doc.get("custom_urgency", "normal"),
            "approver_id": doc.get("custom_approver_id"),
            "supplier_id": doc.get("supplier"),
            "supplier_name": doc.get("supplier_name"),
            "contact_email": doc.get("custom_contact_email"),
            "expected_date": doc.get("schedule_date"),
            "priority": doc.get("custom_priority", "normal"),
            "po_no": doc.get("po_no"),
            "received_qty": doc.get("per_received"),
            "invoice_ref": doc.get("custom_invoice_ref"),
            "created_at": doc.get("creation"),
            "updated_at": doc.get("modified"),
        }

    def _to_erpnext_format(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "doctype": self.doctype,
            "company": "Test Company",
            "supplier": data.get("supplier_id") or "Default Supplier",
            "currency": "EUR",
            "items": [
                {
                    "item_code": "STOCK_ITEM_2",
                    "qty": data.get("quantity") or 1,
                    "rate": data.get("budget") or 0,
                    "warehouse": "Default Warehouse - TC",
                }
            ],
            "schedule_date": data.get("expected_date") or "2099-12-31",
            "custom_requester_id": data.get("requester_id"),
            "custom_item_name": data.get("item_name"),
            "custom_category": data.get("category"),
            "custom_quantity": data.get("quantity"),
            "custom_budget": data.get("budget"),
            "custom_business_reason": data.get("business_reason"),
            "custom_urgency": data.get("urgency", "normal"),
            "custom_supplier_name": data.get("supplier_name"),
            "custom_contact_email": data.get("contact_email"),
            "custom_priority": data.get("priority", "normal"),
            "po_no": data.get("po_no"),
            "custom_invoice_ref": data.get("invoice_ref"),
        }

    def _local_status_to_erpnext(self, local_status: str) -> dict[str, Any]:
        status_map = {
            "draft": {"custom_status": "draft", "docstatus": 0},
            "pending_approval": {"custom_status": "pending_approval", "docstatus": 0},
            "approved": {"custom_status": "approved", "docstatus": 1},
            "ordered": {"custom_status": "ordered", "docstatus": 1},
            "received": {"custom_status": "received", "docstatus": 1, "per_received": 100},
            "invoiced": {"custom_status": "invoiced", "docstatus": 1, "per_billed": 100},
            "completed": {"custom_status": "completed", "docstatus": 1},
        }
        return status_map.get(local_status, {})

    def _erpnext_status_to_local(self, doc: dict[str, Any]) -> str:
        return doc.get("custom_status", "draft")
