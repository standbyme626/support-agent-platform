from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.erpnext_client import ERPNextClient
from app.domain.systems.base import SystemAction

if TYPE_CHECKING:
    from app.domain.systems.adapters.config import ERPNextConfig

CRM_LIFECYCLE = (
    "new",
    "assigned",
    "in_progress",
    "pending",
    "resolved",
    "closed",
)

CRM_ACTIONS = {
    "assign": SystemAction(
        name="assign",
        allowed_from=frozenset({"new"}),
        to_status="assigned",
        required_fields=("assigned_to",),
    ),
    "work_on": SystemAction(
        name="work_on",
        allowed_from=frozenset({"assigned"}),
        to_status="in_progress",
        required_fields=(),
    ),
    "set_pending": SystemAction(
        name="set_pending",
        allowed_from=frozenset({"in_progress"}),
        to_status="pending",
        required_fields=("pending_reason",),
    ),
    "resume": SystemAction(
        name="resume",
        allowed_from=frozenset({"pending"}),
        to_status="in_progress",
        required_fields=(),
    ),
    "resolve": SystemAction(
        name="resolve",
        allowed_from=frozenset({"in_progress", "pending"}),
        to_status="resolved",
        required_fields=("resolution",),
    ),
    "close": SystemAction(
        name="close",
        allowed_from=frozenset({"resolved"}),
        to_status="closed",
        required_fields=(),
    ),
    "reopen": SystemAction(
        name="reopen",
        allowed_from=frozenset({"resolved", "closed"}),
        to_status="new",
        required_fields=("reopen_reason",),
    ),
}


class ERPNextCrmAdapter(ERPNextAdapter):
    def __init__(
        self,
        client: ERPNextClient | None = None,
        config: "ERPNextConfig | None" = None,
    ):
        super().__init__(client, config)

    @property
    def doctype(self) -> str:
        return "Customer"

    @property
    def system_key(self) -> str:
        return "crm"

    @property
    def entity_type(self) -> str:
        return "crm_case"

    @property
    def id_prefix(self) -> str:
        return "CRM-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return CRM_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "closed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return CRM_ACTIONS

    def _to_local_format(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": doc.get("name"),
            "status": doc.get("custom_status", "new"),
            "case_type": doc.get("type") or doc.get("lead_type"),
            "customer_id": doc.get("customer"),
            "customer_name": doc.get("lead_name") or doc.get("company_name"),
            "contact_email": doc.get("email_id") or doc.get("custom_contact_email"),
            "contact_phone": doc.get("phone") or doc.get("mobile_no"),
            "subject": doc.get("subject") or doc.get("name"),
            "description": doc.get("notes") or doc.get("description"),
            "priority": doc.get("priority", "medium"),
            "assigned_to": doc.get("lead_owner") or doc.get("custom_assigned_to"),
            "resolution": doc.get("custom_resolution"),
            "closed_at": doc.get("custom_closed_at"),
            "opportunity_value": doc.get("custom_opportunity_value"),
            "sales_stage": doc.get("custom_sales_stage"),
            "expected_close": doc.get("custom_expected_close"),
            "created_at": doc.get("creation"),
            "updated_at": doc.get("modified"),
        }

    def _to_erpnext_format(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "doctype": self.doctype,
            "customer_name": data.get("customer_name"),
            "customer_type": "Company",
            "customer_group": data.get("customer_group") or "All Customer Groups",
            "territory": data.get("territory") or "All Territories",
            "email_id": data.get("contact_email"),
            "phone": data.get("contact_phone"),
            "mobile_no": data.get("contact_phone"),
        }

    def _local_status_to_erpnext(self, local_status: str) -> dict[str, Any]:
        status_map = {
            "new": {"custom_status": "new", "status": "Open"},
            "assigned": {"custom_status": "assigned", "status": "Assigned"},
            "in_progress": {"custom_status": "in_progress", "status": "Working"},
            "pending": {"custom_status": "pending", "status": "Pending"},
            "resolved": {"custom_status": "resolved", "status": "Closed"},
            "closed": {"custom_status": "closed", "status": "Closed"},
        }
        return status_map.get(local_status, {})

    def _erpnext_status_to_local(self, doc: dict[str, Any]) -> str:
        return doc.get("custom_status", "new")
