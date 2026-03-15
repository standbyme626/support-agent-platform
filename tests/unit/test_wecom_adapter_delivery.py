from __future__ import annotations

import json

import httpx
import pytest
from pytest import MonkeyPatch

from channel_adapters.base import ChannelAdapterError
from channel_adapters.wecom_adapter import WeComAdapter
from storage.models import OutboundEnvelope


def test_wecom_delivery_returns_render_only_when_api_disabled(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("WECOM_APP_API_ENABLED", raising=False)
    adapter = WeComAdapter()
    outbound = OutboundEnvelope(
        channel="wecom",
        session_id="dm:user_001",
        body="hello",
        metadata={},
    )

    rendered = adapter.build_outbound(outbound)
    delivery = adapter.deliver_outbound(outbound=outbound, payload=rendered)

    assert delivery["mode"] == "render_only"


def test_wecom_delivery_sends_message_via_message_send_api(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WECOM_APP_API_ENABLED", "1")
    monkeypatch.setenv("WECOM_BOT_ID", "corp-id-demo")
    monkeypatch.setenv("WECOM_AGENT_SECRET", "corp-secret-demo")
    monkeypatch.setenv("WECOM_AGENT_ID", "1000002")

    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        if request.url.path == "/cgi-bin/gettoken":
            return httpx.Response(
                status_code=200,
                json={"errcode": 0, "errmsg": "ok", "access_token": "token-demo", "expires_in": 7200},
            )
        if request.url.path == "/cgi-bin/message/send":
            assert request.url.params.get("access_token") == "token-demo"
            body = json.loads(request.content.decode("utf-8"))
            assert body["touser"] == "user_001"
            assert body["agentid"] == "1000002"
            return httpx.Response(status_code=200, json={"errcode": 0, "errmsg": "ok"})
        return httpx.Response(status_code=404, json={"errcode": 404, "errmsg": "not_found"})

    adapter = WeComAdapter(transport=httpx.MockTransport(handler))
    outbound = OutboundEnvelope(
        channel="wecom",
        session_id="dm:user_001",
        body="真实发送测试",
        metadata={},
    )
    rendered = adapter.build_outbound(outbound)
    delivery = adapter.deliver_outbound(outbound=outbound, payload=rendered)

    assert delivery["mode"] == "api_sent"
    assert delivery["action"] == "message_send"
    assert len(requests_seen) == 2


def test_wecom_delivery_uses_group_api_for_collab_dispatch(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WECOM_APP_API_ENABLED", "1")
    monkeypatch.setenv("WECOM_BOT_ID", "corp-id-demo")
    monkeypatch.setenv("WECOM_AGENT_SECRET", "corp-secret-demo")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/gettoken":
            return httpx.Response(
                status_code=200,
                json={"errcode": 0, "errmsg": "ok", "access_token": "token-demo", "expires_in": 7200},
            )
        if request.url.path == "/cgi-bin/appchat/send":
            assert request.url.params.get("access_token") == "token-demo"
            body = json.loads(request.content.decode("utf-8"))
            assert body["chatid"] == "ops-room"
            return httpx.Response(status_code=200, json={"errcode": 0, "errmsg": "ok"})
        return httpx.Response(status_code=404, json={"errcode": 404, "errmsg": "not_found"})

    adapter = WeComAdapter(transport=httpx.MockTransport(handler))
    outbound = OutboundEnvelope(
        channel="wecom",
        session_id="group:ops-room:user:u_dispatch_bot",
        body="协同派单消息",
        metadata={"outbound_type": "collab_dispatch", "target_group_id": "ops-room"},
    )
    rendered = adapter.build_outbound(outbound)
    delivery = adapter.deliver_outbound(outbound=outbound, payload=rendered)

    assert delivery["mode"] == "api_sent"
    assert delivery["action"] == "appchat_send"


def test_wecom_delivery_marks_retryable_on_token_expired(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WECOM_APP_API_ENABLED", "1")
    monkeypatch.setenv("WECOM_BOT_ID", "corp-id-demo")
    monkeypatch.setenv("WECOM_AGENT_SECRET", "corp-secret-demo")
    monkeypatch.setenv("WECOM_AGENT_ID", "1000002")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/gettoken":
            return httpx.Response(
                status_code=200,
                json={"errcode": 0, "errmsg": "ok", "access_token": "token-demo", "expires_in": 7200},
            )
        if request.url.path == "/cgi-bin/message/send":
            return httpx.Response(
                status_code=200,
                json={"errcode": 42001, "errmsg": "access_token expired"},
            )
        return httpx.Response(status_code=404, json={"errcode": 404, "errmsg": "not_found"})

    adapter = WeComAdapter(transport=httpx.MockTransport(handler))
    outbound = OutboundEnvelope(
        channel="wecom",
        session_id="dm:user_001",
        body="token 失效重试",
        metadata={},
    )
    rendered = adapter.build_outbound(outbound)

    with pytest.raises(ChannelAdapterError) as excinfo:
        adapter.deliver_outbound(outbound=outbound, payload=rendered)
    assert excinfo.value.code == "wecom_message_send_failed"
    assert excinfo.value.retryable is True
