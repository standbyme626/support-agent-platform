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
    assert ticket.inbox == "telegram"
    assert ticket.source_channel == "telegram"
    assert ticket.risk_level == "medium"

    assigned = api.assign_ticket(ticket.ticket_id, assignee="agent-a", actor_id="lead")
    assert assigned.assignee == "agent-a"
    assert assigned.status == "pending"
    assert assigned.lifecycle_stage == "classified"

    updated = api.update_ticket(
        ticket.ticket_id,
        {"latest_message": "已上传账单截图", "metadata": {"attachment": True}},
        actor_id="agent-a",
    )
    assert updated.metadata["attachment"] is True

    escalated = api.escalate_ticket(ticket.ticket_id, actor_id="agent-a", reason="高风险")
    assert escalated.status == "escalated"
    assert escalated.priority == "P1"
    assert escalated.lifecycle_stage == "awaiting_human"
    assert escalated.escalated_at is not None

    closed = api.close_ticket(
        ticket.ticket_id,
        actor_id="agent-a",
        resolution_note="已退款",
        close_reason="refund_completed",
        resolution_code="BILLING_REFUND",
    )
    assert closed.status == "closed"
    assert closed.lifecycle_stage == "closed"
    assert closed.resolution_note == "已退款"
    assert closed.close_reason == "refund_completed"
    assert closed.resolution_code == "BILLING_REFUND"
    assert closed.closed_at is not None

    reopened = api.reopen_ticket(
        ticket.ticket_id,
        actor_id="agent-a",
        reason="客户反馈问题复现",
    )
    assert reopened.status == "open"
    assert reopened.handoff_state == "in_progress"
    assert reopened.lifecycle_stage == "awaiting_human"
    assert reopened.resolution_note is None
    assert reopened.closed_at is None

    events = api.list_events(ticket.ticket_id)
    assert len(events) >= 7
    event_types = [event.event_type for event in events]
    assert "ticket_created" in event_types
    assert "ticket_assigned" in event_types
    assert "ticket_escalated" in event_types
    assert "ticket_resolved" in event_types
    assert "ticket_closed" in event_types
    assert "ticket_reopened" in event_types
