from __future__ import annotations

from core.hitl.approval_policy import ApprovalPolicy
from storage.models import Ticket


def _ticket() -> Ticket:
    return Ticket(
        ticket_id="TCK-APPROVAL-POLICY",
        channel="wecom",
        session_id="session-approval-policy",
        thread_id="thread-approval-policy",
        customer_id=None,
        title="审批策略测试",
        latest_message="需要升级处理",
        intent="repair",
        priority="P2",
        status="pending",
        queue="support",
        assignee="u_ops_01",
        needs_handoff=False,
    )


def test_approval_policy_flags_escalate_and_sensitive_reassign() -> None:
    policy = ApprovalPolicy.default()
    ticket = _ticket()

    escalate = policy.evaluate(
        action_type="escalate", ticket=ticket, payload={"actor_id": "u_ops_01"}
    )
    assert escalate.requires_approval is True
    assert escalate.rule_id == "approval.escalate"

    sensitive_reassign = policy.evaluate(
        action_type="reassign",
        ticket=ticket,
        payload={"actor_id": "u_ops_01", "target_queue": "security"},
    )
    assert sensitive_reassign.requires_approval is True
    assert sensitive_reassign.rule_id == "approval.reassign_sensitive"

    normal_reassign = policy.evaluate(
        action_type="reassign",
        ticket=ticket,
        payload={"actor_id": "u_ops_01", "target_queue": "support"},
    )
    assert normal_reassign.requires_approval is False
