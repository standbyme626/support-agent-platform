from __future__ import annotations

from pathlib import Path

from channel_adapters.telegram_adapter import TelegramAdapter
from core.trace_logger import JsonTraceLogger
from openclaw_adapter.bindings import GatewayBindings
from openclaw_adapter.channel_router import ChannelRouter
from openclaw_adapter.gateway import OpenClawGateway
from openclaw_adapter.session_mapper import SessionMapper


def test_gateway_replay_guard_regression(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "trace.log"
    gateway = OpenClawGateway(
        GatewayBindings(
            channel_router=ChannelRouter({"telegram": TelegramAdapter()}),
            session_mapper=SessionMapper(sqlite_path),
            trace_logger=JsonTraceLogger(log_path),
        )
    )

    payload = {"update_id": 1001, "message": {"chat": {"id": 42}, "text": "hello"}}
    first = gateway.receive("telegram", payload)
    second = gateway.receive("telegram", payload)
    invalid = gateway.receive("telegram", {"message": {"text": "missing chat"}})

    assert first["status"] == "ok"
    assert second["status"] == "duplicate_ignored"
    assert invalid["status"] == "invalid_payload"
    assert invalid["error"]["code"] == "missing_session_id"
