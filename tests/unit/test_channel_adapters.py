from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from channel_adapters.base import ChannelAdapterError
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


def test_wecom_adapter_builds_inbound() -> None:
    adapter = WeComAdapter()
    inbound = adapter.build_inbound({"FromUserName": "user_a", "Content": "报修", "MsgId": "mid-1"})

    assert inbound.channel == "wecom"
    assert inbound.session_id == "user_a"
    assert inbound.message_text == "报修"
    assert inbound.metadata["inbox"] == "wecom.default"
    assert inbound.metadata["external_message_id"] == "mid-1"


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
