from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.erpnext_client import ERPNextClient
from app.domain.systems.base import SystemAction

if TYPE_CHECKING:
    from app.domain.systems.adapters.config import ERPNextConfig

FINANCE_LIFECYCLE = (
    "invoice_received",
    "matching",
    "exception_flagged",
    "pending_review",
    "approved_for_payment",
    "paid",
    "settled",
)

FINANCE_ACTIONS = {
    "match": SystemAction(
        name="match",
        allowed_from=frozenset({"invoice_received"}),
        to_status="matching",
        required_fields=("match_reference",),
    ),
    "flag_exception": SystemAction(
        name="flag_exception",
        allowed_from=frozenset({"matching"}),
        to_status="exception_flagged",
        required_fields=("exception_reason",),
    ),
    "submit_review": SystemAction(
        name="submit_review",
        allowed_from=frozenset({"exception_flagged"}),
        to_status="pending_review",
        required_fields=("reviewer_id",),
    ),
    "approve_payment": SystemAction(
        name="approve_payment",
        allowed_from=frozenset({"pending_review"}),
        to_status="approved_for_payment",
        required_fields=("approver_id",),
    ),
    "mark_paid": SystemAction(
        name="mark_paid",
        allowed_from=frozenset({"approved_for_payment"}),
        to_status="paid",
        required_fields=("payment_txn_id",),
    ),
    "settle": SystemAction(
        name="settle",
        allowed_from=frozenset({"paid"}),
        to_status="settled",
        required_fields=(),
    ),
}


class ERPNextFinanceAdapter(ERPNextAdapter):
    def __init__(
        self,
        client: ERPNextClient | None = None,
        config: "ERPNextConfig | None" = None,
    ):
        super().__init__(client, config)

    @property
    def doctype(self) -> str:
        return "Purchase Invoice"

    @property
    def system_key(self) -> str:
        return "finance"

    @property
    def entity_type(self) -> str:
        return "finance_invoice"

    @property
    def id_prefix(self) -> str:
        return "INV-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return FINANCE_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "settled"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return FINANCE_ACTIONS

    def _to_local_format(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": doc.get("name"),
            "status": doc.get("custom_status", "invoice_received"),
            "vendor_id": doc.get("supplier"),
            "invoice_no": doc.get("bill_no"),
            "po_no": doc.get("po_no"),
            "receipt_no": doc.get("receipt_no"),
            "amount": doc.get("base_net_total"),
            "currency": doc.get("currency", "CNY"),
            "invoice_date": doc.get("bill_date"),
            "tax_amount": doc.get("total_taxes_and_charges"),
            "total_amount": doc.get("grand_total"),
            "payment_terms": doc.get("payment_terms"),
            "due_date": doc.get("due_date"),
            "payment_method": doc.get("mode_of_payment"),
            "account_id": doc.get("credit_to"),
            "created_at": doc.get("creation"),
            "updated_at": doc.get("modified"),
        }

    def _to_erpnext_format(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "doctype": self.doctype,
            "company": "Test Company",
            "supplier": data.get("vendor_id") or "Default Supplier",
            "bill_no": data.get("invoice_no"),
            "po_no": data.get("po_no"),
            "bill_date": data.get("invoice_date") or "2026-01-01",
            "due_date": data.get("due_date") or "2026-12-31",
            "currency": data.get("currency", "CNY"),
            "total_taxes_and_charges": data.get("tax_amount"),
            "grand_total": data.get("total_amount") or 0,
            "items": [
                {
                    "item_code": "STOCK_ITEM",
                    "qty": 1,
                    "rate": data.get("total_amount") or 0,
                }
            ],
        }

    def _local_status_to_erpnext(self, local_status: str) -> dict[str, Any]:
        status_map = {
            "invoice_received": {"custom_status": "invoice_received", "docstatus": 0},
            "matching": {"custom_status": "matching", "docstatus": 0},
            "exception_flagged": {"custom_status": "exception_flagged", "docstatus": 0},
            "pending_review": {"custom_status": "pending_review", "docstatus": 0},
            "approved_for_payment": {"custom_status": "approved_for_payment", "docstatus": 1},
            "paid": {"custom_status": "paid", "docstatus": 1, "outstanding_amount": 0},
            "settled": {"custom_status": "settled", "docstatus": 1, "outstanding_amount": 0},
        }
        return status_map.get(local_status, {})

    def _erpnext_status_to_local(self, doc: dict[str, Any]) -> str:
        return doc.get("custom_status", "invoice_received")
