from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import pytest

from channel_adapters.base import BaseChannelAdapter, ChannelAdapterError
from channel_adapters.feishu_adapter import FeishuAdapter
from channel_adapters.telegram_adapter import TelegramAdapter
from channel_adapters.wecom_adapter import WeComAdapter


def test_feishu_adapter_builds_inbound() -> None:
    adapter = FeishuAdapter()
    inbound = adapter.build_inbound(
        {
            "event": {
                "sender": {"sender_id": {"open_id": "ou_xxx"}},
                "message": {"text": "hello", "message_id": "m-1"},
            },
            "tenant_key": "tenant-1",
        }
    )

    assert inbound.channel == "feishu"
    assert inbound.session_id == "ou_xxx"
    assert inbound.message_text == "hello"
    assert inbound.metadata["inbox"] == "feishu.default"
    assert inbound.metadata["external_message_id"] == "m-1"
    assert inbound.metadata["contract_version"] == "feishu.v2"


def test_telegram_adapter_builds_inbound() -> None:
    adapter = TelegramAdapter()
    inbound = adapter.build_inbound(
        {"update_id": 1, "message": {"chat": {"id": 99, "username": "alice"}, "text": "hi"}}
    )

    assert inbound.channel == "telegram"
    assert inbound.session_id == "99"
    assert inbound.message_text == "hi"
    assert inbound.metadata["inbox"] == "telegram.default"
    assert inbound.metadata["external_message_id"] == 1
    assert inbound.metadata["contract_version"] == "telegram.v2"


def test_wecom_adapter_builds_inbound() -> None:
    adapter = WeComAdapter()
    inbound = adapter.build_inbound({"FromUserName": "user_a", "Content": "报修", "MsgId": "mid-1"})

    assert inbound.channel == "wecom"
    assert inbound.session_id == "user_a"
    assert inbound.message_text == "报修"
    assert inbound.metadata["inbox"] == "wecom.default"
    assert inbound.metadata["external_message_id"] == "mid-1"
    assert inbound.metadata["contract_version"] == "wecom.v2"


def test_wecom_adapter_prefers_explicit_session_id() -> None:
    adapter = WeComAdapter()
    inbound = adapter.build_inbound(
        {
            "session_id": "group:g-1:user:user_a",
            "FromUserName": "user_a",
            "Content": "群内报修",
            "CreateTime": "1710000001",
        }
    )

    assert inbound.session_id == "group:g-1:user:user_a"
    assert (
        adapter.idempotency_key(
            {
                "session_id": "group:g-1:user:user_a",
                "FromUserName": "user_a",
                "CreateTime": "1710000001",
            }
        )
        == "wecom:group:g-1:user:user_a:1710000001"
    )


def test_feishu_signature_verification() -> None:
    adapter = FeishuAdapter()
    secret = "feishu-secret"
    timestamp = str(int(time.time()))
    nonce = "nonce-1"
    signature = hmac.new(
        secret.encode(),
        f"{timestamp}:{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()
    adapter.verify_inbound(
        {
            "signature": signature,
            "secret": secret,
            "timestamp": timestamp,
            "nonce": nonce,
        }
    )

    with pytest.raises(ChannelAdapterError):
        adapter.verify_inbound(
            {
                "signature": "bad-signature",
                "secret": secret,
                "timestamp": timestamp,
                "nonce": nonce,
            }
        )


def test_wecom_signature_verification() -> None:
    adapter = WeComAdapter()
    secret = "wecom-secret"
    timestamp = str(int(time.time()))
    nonce = "nonce-2"
    signature = hmac.new(
        secret.encode(),
        f"{timestamp}:{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()
    adapter.verify_inbound(
        {
            "signature": signature,
            "secret": secret,
            "timestamp": timestamp,
            "nonce": nonce,
        }
    )


def test_wecom_signature_source_validation() -> None:
    adapter = WeComAdapter()
    secret = "wecom-secret"
    timestamp = str(int(time.time()))
    nonce = "nonce-source"
    signature = hmac.new(
        secret.encode(),
        f"{timestamp}:{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()

    adapter.verify_inbound(
        {
            "signature": signature,
            "secret": secret,
            "timestamp": timestamp,
            "nonce": nonce,
            "source": "wecom_bridge",
            "require_source_validation": True,
        }
    )

    with pytest.raises(ChannelAdapterError) as exc_info:
        adapter.verify_inbound(
            {
                "signature": signature,
                "secret": secret,
                "timestamp": timestamp,
                "nonce": nonce,
                "source": "untrusted",
                "require_source_validation": True,
            }
        )
    assert exc_info.value.code == "invalid_source"


def test_channel_idempotency_key_fallbacks() -> None:
    telegram = TelegramAdapter()
    assert (
        telegram.idempotency_key(
            {"message": {"chat": {"id": 88}, "message_id": 901, "text": "hi"}}
        )
        == "telegram:88:901"
    )

    feishu = FeishuAdapter()
    assert (
        feishu.idempotency_key(
            {
                "event_id": "evt_1",
                "event": {"message": {"text": "hello"}, "sender": {"sender_id": {"open_id": "u1"}}},
            }
        )
        == "feishu:evt_1"
    )

    wecom = WeComAdapter()
    assert (
        wecom.idempotency_key(
            {"FromUserName": "user-a", "CreateTime": "1710000000", "Content": "ok"}
        )
        == "wecom:user-a:1710000000"
    )


@pytest.mark.parametrize(
    ("adapter", "payload", "code"),
    [
        (TelegramAdapter(), {"message": {"text": "missing chat id"}}, "missing_session_id"),
        (TelegramAdapter(), {"message": {"chat": {"id": 1}}}, "missing_message_text"),
        (
            FeishuAdapter(),
            {"event": {"sender": {"sender_id": {"open_id": "ou_1"}}}},
            "missing_message_text",
        ),
        (WeComAdapter(), {"Content": "missing sender"}, "missing_session_id"),
    ],
)
def test_adapter_missing_required_fields_raise_contract_errors(
    adapter: BaseChannelAdapter, payload: dict[str, Any], code: str
) -> None:
    with pytest.raises(ChannelAdapterError) as exc_info:
        adapter.build_inbound(payload)

    assert exc_info.value.code == code
