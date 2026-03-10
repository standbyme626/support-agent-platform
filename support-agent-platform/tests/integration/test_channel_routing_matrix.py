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


def test_gateway_channel_routing_matrix(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "trace.log"
    gateway = OpenClawGateway(
        GatewayBindings(
            channel_router=ChannelRouter(
                {"feishu": FeishuAdapter(), "telegram": TelegramAdapter(), "wecom": WeComAdapter()}
            ),
            session_mapper=SessionMapper(sqlite_path),
            trace_logger=JsonTraceLogger(log_path),
        )
    )

    responses = [
        gateway.receive(
            "telegram",
            {"trace_id": "trace_chan_tg", "message": {"chat": {"id": 1}, "text": "hi"}},
        ),
        gateway.receive(
            "feishu",
            {
                "trace_id": "trace_chan_fs",
                "event": {
                    "sender": {"sender_id": {"open_id": "ou_1"}},
                    "message": {"text": "hello", "message_id": "m1"},
                },
            },
        ),
        gateway.receive(
            "wecom",
            {"trace_id": "trace_chan_wc", "FromUserName": "u1", "Content": "yo", "MsgId": "m2"},
        ),
    ]

    assert all(response["status"] == "ok" for response in responses)
    assert all(str(response["trace_id"]).startswith("trace_") for response in responses)
