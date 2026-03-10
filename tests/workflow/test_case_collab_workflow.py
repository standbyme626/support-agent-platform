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
    assert escalate.ticket.status == "escalated"
    assert escalate.ticket.handoff_state == "pending_approval"

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
        command_line="/close resolved with firmware reset",
    )
    assert closed.ticket.status == "closed"
    assert closed.ticket.handoff_state == "completed"
    assert "final_action_trail" in closed.ticket.metadata
