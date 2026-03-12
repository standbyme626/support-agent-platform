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


def test_session_mapper_records_replay_events(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "session.db"
    mapper = SessionMapper(sqlite_path)
    mapper.get_or_create("session-3", {"channel": "telegram"})

    accepted, first_binding = mapper.record_idempotency_key(
        session_id="session-3",
        idempotency_key="telegram:1001",
        trace_id="trace-1",
        channel="telegram",
    )
    duplicate, second_binding = mapper.record_idempotency_key(
        session_id="session-3",
        idempotency_key="telegram:1001",
        trace_id="trace-2",
        channel="telegram",
    )

    assert accepted is True
    assert duplicate is False
    assert first_binding.metadata["last_message_id"] == "telegram:1001"
    assert int(second_binding.metadata["replay_count"]) == 1
    replay_events = mapper.list_replay_events(limit=10)
    assert len(replay_events) == 1
    assert replay_events[0]["idempotency_key"] == "telegram:1001"
