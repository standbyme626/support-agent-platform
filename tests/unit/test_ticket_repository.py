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

    assert rolled_back == "0003_add_ticket_lifecycle_columns"
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
        },
    )
    assert updated.lifecycle_stage == "awaiting_human"
    assert updated.escalated_at is not None
    assert updated.resolution_note == "need on-call engineer"
