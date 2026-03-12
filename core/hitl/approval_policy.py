from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from storage.models import Ticket


@dataclass(frozen=True)
class ApprovalRequirement:
    requires_approval: bool
    risk_level: str
    reason: str
    rule_id: str
    policy_version: str


class ApprovalPolicy:
    """High-risk action classifier for HITL approvals."""

    def __init__(
        self,
        *,
        policy_version: str = "approval-policy-v1",
        sensitive_reassign_queues: set[str] | None = None,
        sensitive_reassign_assignees: set[str] | None = None,
    ) -> None:
        self._policy_version = policy_version
        self._sensitive_reassign_queues = {
            item.lower()
            for item in (sensitive_reassign_queues or {"security", "legal", "finance-critical"})
        }
        self._sensitive_reassign_assignees = {
            item.lower()
            for item in (
                sensitive_reassign_assignees or {"security_oncall", "legal_lead", "finance_owner"}
            )
        }

    @classmethod
    def default(cls) -> ApprovalPolicy:
        return cls()

    @property
    def policy_version(self) -> str:
        return self._policy_version

    def evaluate(
        self,
        *,
        action_type: str,
        ticket: Ticket,
        payload: Mapping[str, Any] | None = None,
    ) -> ApprovalRequirement:
        action = action_type.strip().lower()
        data = dict(payload or {})

        if action == "escalate":
            return ApprovalRequirement(
                requires_approval=True,
                risk_level="high",
                reason="escalation_requires_manual_confirmation",
                rule_id="approval.escalate",
                policy_version=self._policy_version,
            )

        if action == "reassign":
            target_queue = str(data.get("target_queue") or "").strip().lower()
            target_assignee = str(data.get("target_assignee") or "").strip().lower()
            if (
                target_queue in self._sensitive_reassign_queues
                or target_assignee in self._sensitive_reassign_assignees
            ):
                return ApprovalRequirement(
                    requires_approval=True,
                    risk_level="high",
                    reason="sensitive_reassign_requires_manual_confirmation",
                    rule_id="approval.reassign_sensitive",
                    policy_version=self._policy_version,
                )

        return ApprovalRequirement(
            requires_approval=False,
            risk_level=str(ticket.risk_level),
            reason="no_approval_required",
            rule_id="approval.none",
            policy_version=self._policy_version,
        )
