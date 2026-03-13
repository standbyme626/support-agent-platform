from __future__ import annotations

from pathlib import Path

from core.ticket_api import TicketAPI
from storage.ticket_repository import TicketRepository
from workflows.case_collab_workflow import CaseCollabWorkflow


def _prepare_ticket(tmp_path: Path) -> tuple[TicketAPI, str]:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    api = TicketAPI(repo)

    ticket = api.create_ticket(
        channel="telegram",
        session_id="session-collab",
        thread_id="thread-collab",
        title="设备故障",
        latest_message="设备无法开机",
        intent="repair",
        queue="support",
    )
    return api, ticket.ticket_id


def test_case_collab_commands_end_to_end(tmp_path: Path) -> None:
    api, ticket_id = _prepare_ticket(tmp_path)
    collab = CaseCollabWorkflow(api)

    pushed = collab.push_new_ticket(ticket_id)
    assert "/claim" in pushed["message"]
    assert "/customer-confirm" in pushed["message"]
    assert "summary=" in pushed["message"]
    assert "similar=" in pushed["message"]
    assert "next=" in pushed["message"]
    assert "risk=" in pushed["message"]
    assert "sla_remaining=" in pushed["message"]

    claim = collab.handle_command(ticket_id=ticket_id, actor_id="agent-a", command_line="/claim")
    assert claim.ticket.assignee == "agent-a"
    assert claim.ticket.handoff_state == "claimed"

    reassign = collab.handle_command(
        ticket_id=ticket_id,
        actor_id="lead-1",
        command_line="/reassign agent-b",
    )
    assert reassign.ticket.assignee == "agent-b"
    assert reassign.ticket.handoff_state == "waiting_internal"

    escalate = collab.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-b",
        command_line="/escalate customer is blocked",
    )
    assert escalate.ticket.status == "pending"
    assert escalate.ticket.handoff_state == "pending_approval"
    assert "pending approval" in escalate.message

    resolved = collab.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-b",
        command_line="/resolve fix prepared and verified",
    )
    assert resolved.ticket.status == "resolved"
    assert resolved.ticket.handoff_state == "waiting_customer"

    closed = collab.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-b",
        command_line="/customer-confirm resolved with firmware reset",
    )
    assert closed.command == "customer-confirm"
    assert closed.ticket.status == "closed"
    assert closed.ticket.handoff_state == "completed"
    assert closed.ticket.close_reason == "customer_confirmed"
    assert "final_action_trail" in closed.ticket.metadata


def test_case_collab_sensitive_reassign_requires_approval(tmp_path: Path) -> None:
    api, ticket_id = _prepare_ticket(tmp_path)
    collab = CaseCollabWorkflow(api)

    collab.push_new_ticket(ticket_id)
    collab.handle_command(ticket_id=ticket_id, actor_id="agent-a", command_line="/claim")
    pending = collab.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-a",
        command_line="/reassign security_oncall",
    )

    assert pending.command == "reassign"
    assert pending.ticket.handoff_state == "pending_approval"
    assert "pending approval" in pending.message


def test_case_collab_supports_close_compat_operator_close_and_end_session(tmp_path: Path) -> None:
    api, ticket_id = _prepare_ticket(tmp_path)
    collab = CaseCollabWorkflow(api)
    collab.push_new_ticket(ticket_id)

    close_compat = collab.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-a",
        command_line="/close customer confirmed stable",
    )
    assert close_compat.command == "close_compat"
    assert close_compat.ticket.status == "closed"
    assert close_compat.ticket.close_reason == "customer_confirmed"
    assert close_compat.ticket.metadata.get("resolved_action") == "close_compat"
    compat_events = api.list_events(ticket_id)
    assert any(item.event_type == "collab_close" for item in compat_events)

    operator_ticket = api.create_ticket(
        channel="telegram",
        session_id="session-collab-operator",
        thread_id="thread-collab-operator",
        title="停车系统异常",
        latest_message="道闸无法落杆",
        intent="repair",
        queue="support",
    )
    operator_closed = collab.handle_command(
        ticket_id=operator_ticket.ticket_id,
        actor_id="agent-b",
        command_line="/operator-close forced close due to safety risk",
    )
    assert operator_closed.command == "operator-close"
    assert operator_closed.ticket.status == "closed"
    assert operator_closed.ticket.close_reason == "operator_forced_close"
    assert operator_closed.ticket.metadata.get("resolved_action") == "operator-close"

    session_ticket = api.create_ticket(
        channel="telegram",
        session_id="session-collab-end",
        thread_id="thread-collab-end",
        title="会话结束测试",
        latest_message="请结束当前会话",
        intent="repair",
        queue="support",
    )
    ended = collab.handle_command(
        ticket_id=session_ticket.ticket_id,
        actor_id="agent-c",
        command_line="/end-session user requested session reset",
    )
    assert ended.command == "end-session"
    events = api.list_events(session_ticket.ticket_id)
    session_end_events = [item for item in events if item.event_type == "collab_session_end_requested"]
    assert session_end_events
    assert session_end_events[-1].payload["session_id"] == "session-collab-end"
