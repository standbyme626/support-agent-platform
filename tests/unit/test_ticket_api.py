from __future__ import annotations

from pathlib import Path

from core.ticket_api import TicketAPI
from openclaw_adapter.session_mapper import SessionMapper
from storage.ticket_repository import TicketRepository


def test_ticket_api_full_lifecycle(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    api = TicketAPI(repo, session_mapper=SessionMapper(sqlite_path))
    ticket = api.create_ticket(
        channel="telegram",
        session_id="s-1",
        thread_id="th-1",
        title="支付问题",
        latest_message="重复扣费",
        intent="billing",
        priority="P2",
        queue="finance",
    )

    assert ticket.status == "open"

    assigned = api.assign_ticket(ticket.ticket_id, assignee="agent-a", actor_id="lead")
    assert assigned.assignee == "agent-a"
    assert assigned.status == "pending"

    updated = api.update_ticket(
        ticket.ticket_id,
        {"latest_message": "已上传账单截图", "metadata": {"attachment": True}},
        actor_id="agent-a",
    )
    assert updated.metadata["attachment"] is True

    escalated = api.escalate_ticket(ticket.ticket_id, actor_id="agent-a", reason="高风险")
    assert escalated.status == "escalated"
    assert escalated.priority == "P1"

    closed = api.close_ticket(ticket.ticket_id, actor_id="agent-a", resolution_note="已退款")
    assert closed.status == "closed"

    events = api.list_events(ticket.ticket_id)
    assert len(events) >= 5
