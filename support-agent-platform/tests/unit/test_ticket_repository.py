from __future__ import annotations

import sqlite3
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

    assert rolled_back == "0002_create_ticket_events"
    assert "ticket_events" not in tables_after_rollback
