from __future__ import annotations

from pathlib import Path

from channel_adapters.feishu_adapter import FeishuAdapter
from channel_adapters.telegram_adapter import TelegramAdapter
from channel_adapters.wecom_adapter import WeComAdapter
from core.trace_logger import JsonTraceLogger
from openclaw_adapter.bindings import GatewayBindings
from openclaw_adapter.channel_router import ChannelRouter
from openclaw_adapter.gateway import OpenClawGateway
from openclaw_adapter.session_mapper import SessionMapper


def test_gateway_ingress_and_ticket_mapping(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "gateway.log"

    bindings = GatewayBindings(
        channel_router=ChannelRouter(
            {
                "feishu": FeishuAdapter(),
                "telegram": TelegramAdapter(),
                "wecom": WeComAdapter(),
            }
        ),
        session_mapper=SessionMapper(sqlite_path),
        trace_logger=JsonTraceLogger(log_path),
    )
    gateway = OpenClawGateway(bindings)

    first = gateway.receive(
        "telegram",
        {
            "update_id": 10,
            "message": {"chat": {"id": 12345, "username": "demo"}, "text": "need help"},
        },
    )
    assert first["status"] == "ok"
    assert first["inbound"]["metadata"]["thread_id"]
    assert first["inbound"]["metadata"]["ticket_id"] is None
    assert first["inbound"]["metadata"]["inbox"] == "telegram.default"
    assert first["inbound"]["metadata"]["contract_version"] == "telegram.v2"
    assert first["inbound"]["metadata"]["idempotency_key_source"] == "update_id"

    duplicated = gateway.receive(
        "telegram",
        {
            "update_id": 10,
            "message": {"chat": {"id": 12345, "username": "demo"}, "text": "need help"},
        },
    )
    assert duplicated["status"] == "duplicate_ignored"

    gateway.bind_ticket("12345", "TICKET-9", metadata={"bound_by": "integration-test"})

    second = gateway.receive(
        "telegram",
        {
            "update_id": 11,
            "message": {"chat": {"id": 12345, "username": "demo"}, "text": "status?"},
        },
    )
    assert second["inbound"]["metadata"]["ticket_id"] == "TICKET-9"
    assert second["inbound"]["metadata"]["inbox"] == "telegram.default"

    invalid = gateway.receive("telegram", {"message": {"text": "missing session"}})
    assert invalid["status"] == "invalid_payload"
    assert invalid["error"]["code"] == "missing_session_id"

    traces = JsonTraceLogger(log_path).read_recent(limit=10)
    assert any(event["event_type"] == "ingress_normalized" for event in traces)
    assert any(event["event_type"] == "egress_rendered" for event in traces)
