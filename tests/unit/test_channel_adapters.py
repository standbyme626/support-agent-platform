from __future__ import annotations

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


def test_telegram_adapter_builds_inbound() -> None:
    adapter = TelegramAdapter()
    inbound = adapter.build_inbound(
        {"update_id": 1, "message": {"chat": {"id": 99, "username": "alice"}, "text": "hi"}}
    )

    assert inbound.channel == "telegram"
    assert inbound.session_id == "99"
    assert inbound.message_text == "hi"


def test_wecom_adapter_builds_inbound() -> None:
    adapter = WeComAdapter()
    inbound = adapter.build_inbound({"FromUserName": "user_a", "Content": "报修", "MsgId": "mid-1"})

    assert inbound.channel == "wecom"
    assert inbound.session_id == "user_a"
    assert inbound.message_text == "报修"
