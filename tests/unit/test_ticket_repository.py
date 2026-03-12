from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from storage.ticket_repository import TicketRepository


def _list_tables(sqlite_path: Path) -> set[str]:
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def test_repository_migrations_apply_and_rollback(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)

    applied = repo.apply_migrations()
    tables_after_apply = _list_tables(sqlite_path)

    assert "0001_create_tickets" in repo.applied_migrations() or "0001_create_tickets" in applied
    assert "tickets" in tables_after_apply
    assert "ticket_events" in tables_after_apply

    rolled_back = repo.rollback_last_migration()
    tables_after_rollback = _list_tables(sqlite_path)

    assert rolled_back == "0004_add_ticket_operational_columns"
    assert "ticket_events" in tables_after_rollback


def test_repository_persists_lifecycle_fields(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    first_due = datetime.now(UTC) + timedelta(minutes=30)
    resolution_due = datetime.now(UTC) + timedelta(hours=8)

    ticket = repo.create_ticket(
        channel="wecom",
        session_id="s-1",
        thread_id="th-1",
        title="设备故障",
        latest_message="无法开机",
        intent="repair",
        priority="P2",
        queue="support",
        inbox="wecom.vip",
        lifecycle_stage="classified",
        first_response_due_at=first_due,
        resolution_due_at=resolution_due,
        source_channel="wecom",
        handoff_state="none",
        risk_level="medium",
    )

    assert ticket.inbox == "wecom.vip"
    assert ticket.lifecycle_stage == "classified"
    assert ticket.first_response_due_at is not None
    assert ticket.resolution_due_at is not None

    escalated_at = datetime.now(UTC)
    updated = repo.update_ticket(
        ticket.ticket_id,
        {
            "lifecycle_stage": "awaiting_human",
            "escalated_at": escalated_at,
            "resolution_note": "need on-call engineer",
            "resolution_code": "NEED_ESCALATION",
            "close_reason": "awaiting_specialist",
            "handoff_state": "requested",
            "last_agent_action": "escalate",
            "risk_level": "high",
        },
    )
    assert updated.lifecycle_stage == "awaiting_human"
    assert updated.escalated_at is not None
    assert updated.resolution_note == "need on-call engineer"
    assert updated.resolution_code == "NEED_ESCALATION"
    assert updated.close_reason == "awaiting_specialist"
    assert updated.handoff_state == "requested"
    assert updated.last_agent_action == "escalate"
    assert updated.risk_level == "high"


def test_repository_event_idempotency_key_deduplicates(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    ticket = repo.create_ticket(
        channel="wecom",
        session_id="s-evt",
        thread_id="th-evt",
        title="重复事件",
        latest_message="需要处理",
        intent="repair",
        priority="P2",
        queue="support",
    )

    first = repo.append_event(
        ticket_id=ticket.ticket_id,
        event_type="ingress_normalized",
        actor_type="system",
        actor_id="test",
        payload={"idempotency_key": "wecom:evt-001"},
    )
    second = repo.append_event(
        ticket_id=ticket.ticket_id,
        event_type="ingress_normalized",
        actor_type="system",
        actor_id="test",
        payload={"idempotency_key": "wecom:evt-001"},
    )

    assert first.event_id == second.event_id
    events = repo.list_events(ticket.ticket_id)
    assert len(events) == 1
