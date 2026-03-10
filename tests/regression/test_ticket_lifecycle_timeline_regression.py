from __future__ import annotations

from pathlib import Path

from core.ticket_api import TicketAPI
from storage.ticket_repository import TicketRepository


def test_ticket_timeline_reconstructable_regression(tmp_path: Path) -> None:
    repo = TicketRepository(tmp_path / "tickets.db")
    repo.apply_migrations()
    api = TicketAPI(repo)

    ticket = api.create_ticket(
        channel="wecom",
        session_id="timeline-1",
        thread_id="th-timeline-1",
        title="设备故障",
        latest_message="设备离线超过 2 小时",
        intent="repair",
        priority="P2",
        queue="support",
    )
    api.assign_ticket(ticket.ticket_id, assignee="agent-a", actor_id="lead")
    api.escalate_ticket(ticket.ticket_id, actor_id="agent-a", reason="SLA risk")
    api.resolve_ticket(
        ticket.ticket_id,
        actor_id="agent-b",
        resolution_note="已远程恢复",
        resolution_code="REMOTE_RECOVERY",
    )
    final_ticket = api.close_ticket(
        ticket.ticket_id,
        actor_id="agent-b",
        resolution_note="客户确认恢复",
        close_reason="customer_confirmed",
        resolution_code="REMOTE_RECOVERY",
    )

    events = api.list_events(ticket.ticket_id)
    event_types = [event.event_type for event in events]

    assert final_ticket.status == "closed"
    assert final_ticket.resolution_code == "REMOTE_RECOVERY"
    assert final_ticket.close_reason == "customer_confirmed"
    assert "ticket_created" in event_types
    assert "ticket_assigned" in event_types
    assert "ticket_escalated" in event_types
    assert "ticket_resolved" in event_types
    assert "ticket_closed" in event_types
