from __future__ import annotations

from pathlib import Path

from core.hitl.approval_policy import ApprovalPolicy
from core.hitl.approval_runtime import ApprovalRuntime
from core.ticket_api import TicketAPI
from storage.ticket_repository import TicketRepository


def _build_runtime(tmp_path: Path) -> tuple[ApprovalRuntime, TicketAPI, str]:
    repo = TicketRepository(tmp_path / "approval_runtime.db")
    repo.apply_migrations()
    ticket_api = TicketAPI(repo)
    ticket = ticket_api.create_ticket(
        channel="wecom",
        session_id="session-approval-runtime",
        thread_id="thread-approval-runtime",
        title="高风险升级",
        latest_message="需要主管审批",
        intent="repair",
        priority="P2",
        queue="support",
    )
    runtime = ApprovalRuntime(ticket_api=ticket_api, policy=ApprovalPolicy.default())
    return runtime, ticket_api, ticket.ticket_id


def test_approval_runtime_request_and_approve(tmp_path: Path) -> None:
    runtime, ticket_api, ticket_id = _build_runtime(tmp_path)
    requested = runtime.request_approval_if_needed(
        ticket_id=ticket_id,
        action_type="escalate",
        actor_id="u_ops_01",
        payload={"actor_id": "u_ops_01", "note": "need escalation"},
        context={"resume_handoff_state": "claimed"},
    )
    assert requested.requires_approval is True
    assert requested.pending_action is not None
    assert requested.ticket.handoff_state == "pending_approval"

    executed_ticket = ticket_api.escalate_ticket(
        ticket_id, actor_id="u_ops_01", reason="approved escalation"
    )
    decision = runtime.mark_approved(
        requested.pending_action.approval_id,
        actor_id="u_supervisor_01",
        execution_ticket=executed_ticket,
    )
    assert decision.pending_action.status == "approved"
    assert decision.ticket.status == "escalated"


def test_approval_runtime_reject_and_timeout(tmp_path: Path) -> None:
    runtime, _, ticket_id = _build_runtime(tmp_path)
    requested = runtime.request_approval_if_needed(
        ticket_id=ticket_id,
        action_type="escalate",
        actor_id="u_ops_01",
        payload={"actor_id": "u_ops_01", "note": "need escalation"},
        context={"resume_handoff_state": "claimed"},
    )
    assert requested.pending_action is not None
    rejected = runtime.mark_rejected(
        requested.pending_action.approval_id,
        actor_id="u_supervisor_02",
        note="insufficient evidence",
    )
    assert rejected.pending_action.status == "rejected"
    assert rejected.ticket.handoff_state == "claimed"

    timeout_requested = runtime.request_approval_if_needed(
        ticket_id=ticket_id,
        action_type="escalate",
        actor_id="u_ops_01",
        payload={"actor_id": "u_ops_01", "note": "need escalation", "timeout_minutes": 0},
        context={"resume_handoff_state": "claimed"},
    )
    assert timeout_requested.pending_action is not None

    pending = runtime.list_pending_actions(ticket_id=ticket_id)
    assert pending == []
    actions = runtime.list_ticket_actions(ticket_id)
    assert any(item.status == "timeout" for item in actions)
