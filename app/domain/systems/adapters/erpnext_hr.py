from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.erpnext_client import ERPNextClient
from app.domain.systems.base import SystemAction

if TYPE_CHECKING:
    from app.domain.systems.adapters.config import ERPNextConfig

HR_LIFECYCLE = (
    "preboarding",
    "submitted",
    "pending_approval",
    "profile_created",
    "provisioning",
    "active",
    "completed",
)

HR_ACTIONS = {
    "send_offer": SystemAction(
        name="send_offer",
        allowed_from=frozenset({"preboarding"}),
        to_status="submitted",
        required_fields=("candidate_name", "position"),
    ),
    "submit": SystemAction(
        name="submit",
        allowed_from=frozenset({"submitted"}),
        to_status="pending_approval",
        required_fields=(),
    ),
    "approve": SystemAction(
        name="approve",
        allowed_from=frozenset({"pending_approval"}),
        to_status="profile_created",
        required_fields=("hr_approver_id",),
    ),
    "create_profile": SystemAction(
        name="create_profile",
        allowed_from=frozenset({"profile_created"}),
        to_status="provisioning",
        required_fields=("employee_id",),
    ),
    "activate": SystemAction(
        name="activate",
        allowed_from=frozenset({"provisioning"}),
        to_status="active",
        required_fields=(),
    ),
    "complete": SystemAction(
        name="complete",
        allowed_from=frozenset({"active"}),
        to_status="completed",
        required_fields=(),
    ),
}


class ERPNextHrAdapter(ERPNextAdapter):
    def __init__(
        self,
        client: ERPNextClient | None = None,
        config: "ERPNextConfig | None" = None,
    ):
        super().__init__(client, config)

    @property
    def doctype(self) -> str:
        return "Employee"

    @property
    def system_key(self) -> str:
        return "hr"

    @property
    def entity_type(self) -> str:
        return "hr_onboarding"

    @property
    def id_prefix(self) -> str:
        return "ONB-"

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return HR_LIFECYCLE

    @property
    def terminal_status(self) -> str:
        return "completed"

    @property
    def actions(self) -> dict[str, SystemAction]:
        return HR_ACTIONS

    def _to_local_format(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": doc.get("name"),
            "status": doc.get("custom_status", "preboarding"),
            "candidate_name": doc.get("employee_name") or doc.get("custom_candidate_name"),
            "department": doc.get("department"),
            "position": doc.get("designation"),
            "manager_id": doc.get("reports_to"),
            "start_date": doc.get("date_of_joining"),
            "employee_id": doc.get("employee_id"),
            "email": doc.get("prefered_email") or doc.get("company_email"),
            "hire_date": doc.get("date_of_joining"),
            "contract_type": doc.get("employment_type"),
            "accounts_json": doc.get("custom_accounts_json", "[]"),
            "devices_json": doc.get("custom_devices_json", "[]"),
            "created_at": doc.get("creation"),
            "updated_at": doc.get("modified"),
        }

    def _to_erpnext_format(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "doctype": self.doctype,
            "first_name": data.get("candidate_name") or "Test",
            "employee_name": data.get("candidate_name") or "Test Employee",
            "department": data.get("department") or "All Departments",
            "designation": data.get("position") or "Staff",
            "reports_to": data.get("manager_id"),
            "date_of_joining": data.get("start_date") or "2026-01-01",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "employee_id": data.get("employee_id"),
            "prefered_email": data.get("email"),
            "employment_type": data.get("contract_type", "Full-time"),
            "company": "Test Company",
            "custom_candidate_name": data.get("candidate_name"),
            "custom_accounts_json": data.get("accounts_json", "[]"),
            "custom_devices_json": data.get("devices_json", "[]"),
        }

    def _local_status_to_erpnext(self, local_status: str) -> dict[str, Any]:
        status_map = {
            "preboarding": {"custom_status": "preboarding", "status": "Left"},
            "submitted": {"custom_status": "submitted", "status": "Left"},
            "pending_approval": {"custom_status": "pending_approval", "status": "Left"},
            "profile_created": {"custom_status": "profile_created", "status": "Active"},
            "provisioning": {"custom_status": "provisioning", "status": "Active"},
            "active": {"custom_status": "active", "status": "Active"},
            "completed": {"custom_status": "completed", "status": "Active"},
        }
        return status_map.get(local_status, {})

    def _erpnext_status_to_local(self, doc: dict[str, Any]) -> str:
        return doc.get("custom_status", "preboarding")
