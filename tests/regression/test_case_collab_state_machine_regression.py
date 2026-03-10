from __future__ import annotations

from pathlib import Path

from core.ticket_api import TicketAPI
from storage.ticket_repository import TicketRepository
from workflows.case_collab_workflow import CaseCollabWorkflow


def test_case_collab_state_machine_regression(tmp_path: Path) -> None:
    repo = TicketRepository(tmp_path / "tickets.db")
    repo.apply_migrations()
    api = TicketAPI(repo)
    collab = CaseCollabWorkflow(api)

    ticket = api.create_ticket(
        channel="telegram",
        session_id="collab-reg-1",
        thread_id="thread-collab-reg-1",
        title="网络波动",
        latest_message="高峰期持续掉线",
        intent="repair",
        queue="support",
    )

    collab.push_new_ticket(ticket.ticket_id)
    claimed = collab.handle_command(
        ticket_id=ticket.ticket_id,
        actor_id="agent-a",
        command_line="/claim",
    )
    escalated = collab.handle_command(
        ticket_id=ticket.ticket_id,
        actor_id="agent-a",
        command_line="/escalate vendor outage",
    )
    resolved = collab.handle_command(
        ticket_id=ticket.ticket_id,
        actor_id="agent-b",
        command_line="/resolve temporary workaround applied",
    )
    closed = collab.handle_command(
        ticket_id=ticket.ticket_id,
        actor_id="agent-b",
        command_line="/close customer confirmed stable",
    )

    assert claimed.ticket.handoff_state == "claimed"
    assert escalated.ticket.handoff_state == "pending_approval"
    assert resolved.ticket.handoff_state == "waiting_customer"
    assert closed.ticket.handoff_state == "completed"
    assert closed.ticket.status == "closed"
