from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.wecom_bridge_server import DEFAULT_REPLY_ON_ERROR, process_wecom_message


class _DummyGateway:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def receive(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((channel, payload))
        return dict(self._response)


@dataclass(frozen=True)
class _DummyIntakeResult:
    reply_text: str
    ticket_id: str
    ticket_action: str


class _DummyIntakeWorkflow:
    def __init__(self, result: _DummyIntakeResult) -> None:
        self._result = result
        self.calls: int = 0

    def run(self, envelope: Any) -> _DummyIntakeResult:
        self.calls += 1
        return self._result


@dataclass(frozen=True)
class _DummyRuntime:
    gateway: _DummyGateway
    intake_workflow: _DummyIntakeWorkflow


def test_process_wecom_message_group_uses_composed_session_id() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:group-1:user:user_a",
                    "message_text": "@机器人 帮我查工单",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已为你创建工单 TICKET-101",
                ticket_id="TICKET-101",
                ticket_action="create_ticket",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-101",
            "chatid": "group-1",
            "chattype": "group",
            "sender_id": "user_a",
            "text": "@机器人 帮我查工单",
            "req_id": "req-101",
        },
    )

    assert result.handled is True
    assert result.status == "ok"
    assert result.reply_text == "已为你创建工单 TICKET-101"
    assert result.ticket_id == "TICKET-101"
    assert runtime.intake_workflow.calls == 1
    assert runtime.gateway.calls[0][0] == "wecom"
    assert runtime.gateway.calls[0][1]["session_id"] == "group:group-1:user:user_a"


def test_process_wecom_message_duplicate_returns_empty_reply() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway({"status": "duplicate_ignored"}),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(reply_text="unused", ticket_id="unused", ticket_action="unused")
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-dup",
            "chatid": "group-1",
            "chattype": "group",
            "sender_id": "user_a",
            "text": "重复消息",
            "req_id": "req-dup",
        },
    )

    assert result.handled is True
    assert result.status == "duplicate_ignored"
    assert result.reply_text == ""
    assert runtime.intake_workflow.calls == 0


def test_process_wecom_message_gateway_error_returns_fallback_reply() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway({"status": "error"}),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(reply_text="unused", ticket_id="unused", ticket_action="unused")
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-error",
            "chattype": "single",
            "sender_id": "user_a",
            "text": "你好",
            "req_id": "req-error",
        },
    )

    assert result.handled is True
    assert result.status == "error"
    assert result.reply_text == DEFAULT_REPLY_ON_ERROR
    assert runtime.intake_workflow.calls == 0


def test_process_wecom_message_accepts_wecom_native_fields() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "dm:user_native",
                    "message_text": "原生字段消息",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已处理企业微信原生字段",
                ticket_id="TICKET-202",
                ticket_action="faq_reply",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "MsgId": "mid-native-1",
            "FromUserName": "user_native",
            "Content": "原生字段消息",
            "ReqId": "req-native-1",
        },
    )

    assert result.handled is True
    assert result.status == "ok"
    assert result.reply_text == "已处理企业微信原生字段"
    assert runtime.intake_workflow.calls == 1
    assert runtime.gateway.calls[0][1]["FromUserName"] == "user_native"
    assert runtime.gateway.calls[0][1]["Content"] == "原生字段消息"
    assert runtime.gateway.calls[0][1]["MsgId"] == "mid-native-1"
