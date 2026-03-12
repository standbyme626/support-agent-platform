from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path

from channel_adapters.feishu_adapter import FeishuAdapter
from channel_adapters.telegram_adapter import TelegramAdapter
from channel_adapters.wecom_adapter import WeComAdapter
from core.trace_logger import JsonTraceLogger
from openclaw_adapter.bindings import GatewayBindings
from openclaw_adapter.channel_router import ChannelRouter
from openclaw_adapter.gateway import OpenClawGateway
from openclaw_adapter.session_mapper import SessionMapper


def _build_gateway(tmp_path: Path) -> OpenClawGateway:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "trace.log"
    return OpenClawGateway(
        GatewayBindings(
            channel_router=ChannelRouter(
                {"feishu": FeishuAdapter(), "telegram": TelegramAdapter(), "wecom": WeComAdapter()}
            ),
            session_mapper=SessionMapper(sqlite_path),
            trace_logger=JsonTraceLogger(log_path),
        )
    )


def test_gateway_channel_routing_matrix(tmp_path: Path) -> None:
    gateway = _build_gateway(tmp_path)

    responses = [
        gateway.receive(
            "telegram",
            {
                "trace_id": "trace_chan_tg",
                "update_id": 101,
                "message": {"chat": {"id": 1}, "text": "hi"},
            },
        ),
        gateway.receive(
            "feishu",
            {
                "trace_id": "trace_chan_fs",
                "event_id": "evt_chan_fs_1",
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


def test_gateway_channel_routing_duplicate_and_invalid_payload(tmp_path: Path) -> None:
    gateway = _build_gateway(tmp_path)

    first_tg = gateway.receive(
        "telegram",
        {"update_id": 3001, "message": {"chat": {"id": 8}, "text": "once"}},
    )
    duplicate_tg = gateway.receive(
        "telegram",
        {"update_id": 3001, "message": {"chat": {"id": 8}, "text": "once"}},
    )

    first_fs = gateway.receive(
        "feishu",
        {
            "event_id": "evt-dup-1",
            "event": {
                "sender": {"sender_id": {"open_id": "ou_dup"}},
                "message": {"text": "once", "message_id": "fs-dup-1"},
            },
        },
    )
    duplicate_fs = gateway.receive(
        "feishu",
        {
            "event_id": "evt-dup-1",
            "event": {
                "sender": {"sender_id": {"open_id": "ou_dup"}},
                "message": {"text": "once", "message_id": "fs-dup-1"},
            },
        },
    )

    first_wc = gateway.receive(
        "wecom",
        {
            "FromUserName": "wc_dup",
            "Content": "once",
            "MsgId": "wc-dup-1",
        },
    )
    duplicate_wc = gateway.receive(
        "wecom",
        {
            "FromUserName": "wc_dup",
            "Content": "once",
            "MsgId": "wc-dup-1",
        },
    )

    assert first_tg["status"] == "ok"
    assert duplicate_tg["status"] == "duplicate_ignored"
    assert first_fs["status"] == "ok"
    assert duplicate_fs["status"] == "duplicate_ignored"
    assert first_wc["status"] == "ok"
    assert duplicate_wc["status"] == "duplicate_ignored"

    invalid_tg = gateway.receive("telegram", {"message": {"text": "missing chat"}})
    invalid_fs = gateway.receive(
        "feishu",
        {"event": {"message": {"text": "missing sender"}}},
    )
    invalid_wc = gateway.receive("wecom", {"Content": "missing sender"})

    assert invalid_tg["status"] == "invalid_payload"
    assert invalid_tg["error"]["code"] == "missing_session_id"
    assert invalid_fs["status"] == "invalid_payload"
    assert invalid_fs["error"]["code"] == "missing_session_id"
    assert invalid_wc["status"] == "invalid_payload"
    assert invalid_wc["error"]["code"] == "missing_session_id"


def test_gateway_wecom_signature_validation_and_audit(tmp_path: Path) -> None:
    gateway = _build_gateway(tmp_path)

    missing_signature = gateway.receive(
        "wecom",
        {
            "FromUserName": "wc_sig",
            "Content": "hello",
            "MsgId": "wc-sig-1",
            "require_signature": True,
            "source": "wecom_bridge",
            "require_source_validation": True,
        },
    )
    assert missing_signature["status"] == "invalid_payload"
    assert missing_signature["error"]["code"] == "missing_signature"

    secret = "integration-secret"
    timestamp = str(int(time.time()))
    nonce = "nonce-int"
    signature = hmac.new(
        secret.encode(),
        f"{timestamp}:{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()
    accepted = gateway.receive(
        "wecom",
        {
            "FromUserName": "wc_sig",
            "Content": "hello signed",
            "MsgId": "wc-sig-2",
            "require_signature": True,
            "source": "wecom_bridge",
            "require_source_validation": True,
            "signature": signature,
            "secret": secret,
            "timestamp": timestamp,
            "nonce": nonce,
        },
    )
    assert accepted["status"] == "ok"

    traces = gateway.bindings.trace_logger.read_recent(limit=30)
    event_types = [item["event_type"] for item in traces]
    assert "signature_rejected" in event_types
    assert "signature_validated" in event_types
