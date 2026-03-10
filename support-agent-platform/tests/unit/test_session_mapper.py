from __future__ import annotations

from pathlib import Path

from openclaw_adapter.session_mapper import SessionMapper


def test_session_mapper_persists_thread_and_metadata(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "session.db"
    mapper = SessionMapper(sqlite_path)

    first = mapper.get_or_create("session-1", {"from": "telegram"})
    second = mapper.get_or_create("session-1", {"lang": "zh-CN"})

    assert first.thread_id == second.thread_id
    assert second.metadata["from"] == "telegram"
    assert second.metadata["lang"] == "zh-CN"


def test_session_mapper_sets_ticket_and_survives_restart(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "session.db"

    mapper = SessionMapper(sqlite_path)
    mapper.get_or_create("session-2", {"source": "feishu"})
    mapper.set_ticket_id("session-2", "TICKET-1001", metadata={"priority": "P1"})

    restarted_mapper = SessionMapper(sqlite_path)
    loaded = restarted_mapper.get("session-2")

    assert loaded is not None
    assert loaded.ticket_id == "TICKET-1001"
    assert loaded.metadata["priority"] == "P1"
