from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from pytest import MonkeyPatch

from scripts.wecom_bridge_server import (
    DEFAULT_REPLY_ON_ERROR,
    _split_outbound_body,
    process_wecom_message,
)


class _DummyGateway:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.outbound_calls: list[dict[str, Any]] = []

    def receive(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((channel, payload))
        return dict(self._response)

    def send_outbound(
        self, *, channel: str, session_id: str, body: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "channel": channel,
            "session_id": session_id,
            "body": body,
            "metadata": dict(metadata),
        }
        self.outbound_calls.append(payload)
        return {"status": "ok"}


@dataclass(frozen=True)
class _DummyIntakeResult:
    reply_text: str
    ticket_id: str
    ticket_action: str
    queue: str = "support"
    priority: str = "P3"
    collab_push: dict[str, Any] | None = None


class _DummyIntakeWorkflow:
    def __init__(self, result: _DummyIntakeResult, *, ticket_api: Any | None = None) -> None:
        self._result = result
        self._ticket_api = ticket_api
        self.calls: int = 0
        self.existing_ticket_ids: list[str | None] = []

    def run(
        self, envelope: Any, *, existing_ticket_id: str | None = None
    ) -> _DummyIntakeResult:
        _ = envelope
        self.calls += 1
        self.existing_ticket_ids.append(existing_ticket_id)
        return self._result


@dataclass(frozen=True)
class _DummyRuntime:
    gateway: _DummyGateway
    intake_workflow: _DummyIntakeWorkflow


class _DummyTicketAPI:
    def __init__(self) -> None:
        self.bind_calls: list[dict[str, Any]] = []

    def bind_session_ticket(
        self,
        session_id: str,
        ticket_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.bind_calls.append(
            {
                "session_id": session_id,
                "ticket_id": ticket_id,
                "metadata": dict(metadata or {}),
            }
        )


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
    assert runtime.intake_workflow.existing_ticket_ids[-1] is None
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


def test_process_wecom_message_accepts_nested_wecom_fields() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:group_nested:user:user_nested",
                    "message_text": "@智慧工单机器人 \\new",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已识别嵌套字段",
                ticket_id="TICKET-303",
                ticket_action="create_ticket",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "message": {"msgid": "mid-nested-1"},
            "from": {"userid": "user_nested"},
            "conversation": {"id": "group_nested"},
            "conversation_type": "group",
            "text": {"content": "@智慧工单机器人 \\new"},
            "trace_id": "trace-nested-1",
        },
    )

    assert result.handled is True
    assert result.status == "ok"
    assert result.reply_text == "已识别嵌套字段"
    assert runtime.intake_workflow.calls == 1
    assert runtime.gateway.calls[0][1]["FromUserName"] == "user_nested"
    assert runtime.gateway.calls[0][1]["Content"] == "@智慧工单机器人 \\new"
    assert runtime.gateway.calls[0][1]["MsgId"] == "mid-nested-1"
    assert runtime.gateway.calls[0][1]["session_id"] == "group:group_nested:user:user_nested"


def test_process_wecom_message_builds_fallback_msg_id_when_msg_id_missing() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "dm:user_no_msgid",
                    "message_text": "你好",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已处理无消息ID场景",
                ticket_id="TICKET-304",
                ticket_action="faq_reply",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "from": {"userid": "user_no_msgid"},
            "message": {"id": "CONST"},
            "text": {"content": "你好"},
            "trace_id": "trace-no-msgid-1",
        },
    )

    assert result.handled is True
    assert result.status == "ok"
    assert result.reply_text == "已处理无消息ID场景"
    fallback_msg_id = runtime.gateway.calls[0][1]["MsgId"]
    assert fallback_msg_id.startswith("bridge:trace-no-msgid-1:")
    assert fallback_msg_id != "CONST"


def test_process_wecom_message_fallback_msg_id_changes_when_content_changes() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "dm:user_req_reused",
                    "message_text": "占位",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="ok",
                ticket_id="TICKET-305",
                ticket_action="faq_reply",
            )
        ),
    )

    process_wecom_message(
        runtime,
        {
            "from": {"userid": "user_req_reused"},
            "text": {"content": "\\new"},
            "ReqId": "REQ-CONST",
        },
    )
    process_wecom_message(
        runtime,
        {
            "from": {"userid": "user_req_reused"},
            "text": {"content": "你好"},
            "ReqId": "REQ-CONST",
        },
    )

    first_msg_id = runtime.gateway.calls[0][1]["MsgId"]
    second_msg_id = runtime.gateway.calls[1][1]["MsgId"]
    assert first_msg_id != second_msg_id


def test_process_wecom_message_accepts_wecom_native_fields() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "dm:user_native",
                    "message_text": "原生字段消息",
                    "metadata": {"inbox": "wecom.default", "ticket_id": "TICKET-202"},
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
    assert runtime.intake_workflow.existing_ticket_ids[-1] == "TICKET-202"
    assert runtime.gateway.calls[0][1]["FromUserName"] == "user_native"
    assert runtime.gateway.calls[0][1]["Content"] == "原生字段消息"
    assert runtime.gateway.calls[0][1]["MsgId"] == "mid-native-1"


def test_process_wecom_message_accepts_sender_user_id_and_chat_id_variants() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:group-variant:user:user_sender_variant",
                    "message_text": "@智慧工单机器人 \\new",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已处理 sender/chat 变体字段",
                ticket_id="TICKET-401",
                ticket_action="create_ticket",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-variant-1",
            "chat_id": "group-variant",
            "chattype": "group",
            "sender": {"user_id": "user_sender_variant"},
            "text": "@智慧工单机器人 \\new",
            "req_id": "req-variant-1",
        },
    )

    assert result.handled is True
    assert result.status == "ok"
    assert result.reply_text == "已处理 sender/chat 变体字段"
    assert runtime.intake_workflow.calls == 1
    assert runtime.gateway.calls[0][1]["FromUserName"] == "user_sender_variant"
    assert (
        runtime.gateway.calls[0][1]["session_id"]
        == "group:group-variant:user:user_sender_variant"
    )


def test_process_wecom_message_splits_long_wecom_outbound_messages(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECOM_BRIDGE_OUTBOUND_CHUNK_CHARS", "200")
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "dm:user_chunk",
                    "message_text": "请给我进度",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="".join(
                    ["第一段说明，第二段说明，第三段说明，第四段说明。" for _ in range(16)]
                ),
                ticket_id="TICKET-CHUNK-001",
                ticket_action="create_ticket",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-chunk-1",
            "chattype": "single",
            "sender_id": "user_chunk",
            "text": "请给我进度",
            "req_id": "req-chunk-1",
        },
    )

    assert result.handled is True
    assert result.status == "ok"
    assert result.reply_text.startswith("第一段说明")
    assert len(runtime.gateway.outbound_calls) >= 2
    assert all(len(item["body"]) <= 200 for item in runtime.gateway.outbound_calls)
    chunked_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if bool(item.get("metadata", {}).get("chunked"))
    ]
    assert chunked_calls
    assert all(item["metadata"]["chunk_total"] >= 2 for item in chunked_calls)


def test_split_outbound_body_prefers_newline_and_sentence_boundaries(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECOM_BRIDGE_OUTBOUND_CHUNK_CHARS", "200")
    body = (
        "第一段用于说明当前故障背景，影响多个工位，需要尽快处理，并补充资产编号与影响范围，便于处理工程师快速接手。\n"
        "第二段用于说明已执行的排查动作，包含重启与网络检测，同时记录关键日志时间点，避免重复排查。\n"
        "第三段用于说明下一步计划与跟进节奏，并附上临时绕行方案与负责人联系方式，确保业务连续。\n"
        "第四段用于记录复盘要点与后续预防措施，作为下一轮处理的输入。\n"
        "第五段补充业务侧反馈与验证结果，标记影响范围变化。\n"
        "第六段补充现场照片索引与处置时间线，便于后续追踪。"
    )

    chunks = _split_outbound_body(channel="wecom", body=body)

    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)
    assert chunks[0].endswith("\n") or chunks[0].endswith("。")
    assert not chunks[0].endswith("，")


def test_process_wecom_message_accepts_plain_group_id_dispatch_target() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-room:user:u_customer",
                    "message_text": "机房空调异常告警",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已创建工单，正在通知处理人员。",
                ticket_id="TCK-PLAIN-TARGET-001",
                ticket_action="create_ticket",
                queue="human-handoff",
                priority="P2",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-plain-target-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer",
            "text": "机房空调异常告警",
            "req_id": "trace-plain-target-1",
            "dispatch_targets": {"inbox:wecom.default": "ops-room"},
        },
    )

    assert result.status == "ok"
    assert result.delivery_status == "dispatched"
    collab_dispatch_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "collab_dispatch"
    ]
    assert len(collab_dispatch_calls) == 1
    assert collab_dispatch_calls[0]["session_id"] == "group:ops-room:user:u_dispatch_bot"


def test_process_wecom_message_collab_push_dispatch_includes_ticket_detail() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-room:user:u_customer",
                    "message_text": "d栋厕所漏水",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已按新会话处理，并创建/关联新工单上下文。",
                ticket_id="TCK-DETAIL-001",
                ticket_action="create_ticket",
                queue="human-handoff",
                priority="P3",
                collab_push={
                    "ticket_id": "TCK-DETAIL-001",
                    "message": "[new-ticket] TCK-DETAIL-001 | summary=d栋厕所漏水 | next=['先 /claim 认领']",
                    "source": "workflow_cross_group_sync",
                },
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-detail-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer",
            "text": "d栋厕所漏水",
            "req_id": "trace-detail-1",
            "dispatch_targets": {"inbox:wecom.default": "group:ops-room"},
        },
    )

    assert result.status == "ok"
    assert result.delivery_status == "dispatched"
    collab_dispatch_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "collab_dispatch"
    ]
    assert len(collab_dispatch_calls) == 1
    collab_body = str(collab_dispatch_calls[0]["body"])
    assert collab_body.startswith("新工单 TCK-DETAIL-001 已创建")
    assert "优先级：普通（P3）" in collab_body
    assert "\n工单详情：" in collab_body
    assert "工单详情：d栋厕所漏水" in collab_body
    assert "[new-ticket]" not in collab_body
    assert "commands:" not in collab_body


def test_process_wecom_message_dispatch_without_collab_push_uses_inbound_text_as_detail() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-room:user:u_customer",
                    "message_text": "D栋厕所漏水，二楼女厕门口持续渗水",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已受理，正在安排处理人员。",
                ticket_id="TCK-DETAIL-FALLBACK-001",
                ticket_action="create_ticket",
                queue="human-handoff",
                priority="P2",
                collab_push=None,
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-detail-fallback-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer",
            "text": "D栋厕所漏水，二楼女厕门口持续渗水",
            "req_id": "trace-detail-fallback-1",
            "dispatch_targets": {"inbox:wecom.default": "group:ops-room"},
        },
    )

    assert result.status == "ok"
    assert result.delivery_status == "dispatched"
    collab_dispatch_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "collab_dispatch"
    ]
    assert len(collab_dispatch_calls) == 1
    collab_body = str(collab_dispatch_calls[0]["body"])
    assert collab_body.startswith("新工单 TCK-DETAIL-FALLBACK-001 已创建")
    assert "\n工单详情：" in collab_body
    assert "D栋厕所漏水，二楼女厕门口持续渗水" in collab_body


def test_process_wecom_message_existing_ticket_supplement_syncs_to_collab_group() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "dm:u_customer",
                    "message_text": "补充：位置在三楼B区男厕门口",
                    "metadata": {"inbox": "wecom.default", "ticket_id": "TCK-SUPP-001"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="已收到补充信息，我们会继续跟进。",
                ticket_id="TCK-SUPP-001",
                ticket_action="create_ticket",
                queue="human-handoff",
                priority="P2",
                collab_push=None,
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-supplement-1",
            "chattype": "single",
            "sender_id": "u_customer",
            "text": "补充：位置在三楼B区男厕门口",
            "req_id": "trace-supplement-1",
            "dispatch_targets": {"inbox:wecom.default": "group:ops-room:user:u_dispatch_bot"},
        },
    )

    assert result.status == "ok"
    assert result.delivery_status == "dispatched"
    collab_dispatch_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "collab_dispatch"
    ]
    assert len(collab_dispatch_calls) == 1
    collab_body = str(collab_dispatch_calls[0]["body"])
    assert collab_body.startswith("工单 TCK-SUPP-001 收到补充信息：")
    assert "三楼B区男厕门口" in collab_body


def test_process_wecom_message_clarification_required_syncs_guidance_to_collab_group() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-room:user:u_customer",
                    "message_text": "这里漏水了",
                    "metadata": {"inbox": "wecom.default", "ticket_id": "TCK-CLARIFY-001"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text="请补充具体楼层、区域和可联系时间。",
                ticket_id="TCK-CLARIFY-001",
                ticket_action="clarification_required",
                queue="human-handoff",
                priority="P3",
                collab_push=None,
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-clarify-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer",
            "text": "这里漏水了",
            "req_id": "trace-clarify-1",
            "dispatch_targets": {"inbox:wecom.default": "group:ops-room:user:u_dispatch_bot"},
        },
    )

    assert result.status == "ok"
    assert result.delivery_status == "dispatched"
    collab_dispatch_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "collab_dispatch"
    ]
    assert len(collab_dispatch_calls) == 1
    collab_body = str(collab_dispatch_calls[0]["body"])
    assert collab_body.startswith("工单 TCK-CLARIFY-001 当前信息待补充")
    assert "补充线索：这里漏水了" in collab_body


def test_process_wecom_message_group_long_reply_uses_fast_group_and_private_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECOM_GROUP_PRIVATE_DETAIL_ASYNC", "1")
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-room:user:u_customer",
                    "message_text": "请尽快安排处理",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text=(
                    "您好，收到您反馈的 D 栋漏水问题。"
                    "我们已升级人工处理并安排处理人员跟进，"
                    "后续将同步维修进展与上门安排，请保持通讯畅通。"
                ),
                ticket_id="TCK-FAST-PRIVATE-001",
                ticket_action="handoff",
                queue="human-handoff",
                priority="P1",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-fast-private-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer",
            "text": "请尽快安排处理",
            "req_id": "trace-fast-private-1",
            "dispatch_targets": {"inbox:wecom.default": "group:ops-room"},
        },
    )

    assert result.status == "ok"
    assert result.reply_text.startswith("已受理，工单 TCK-FAST-PRIVATE-001 已创建")
    assert "高（P1）" in result.reply_text

    user_receipt_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "user_receipt"
    ]
    assert user_receipt_calls
    assert user_receipt_calls[0]["metadata"].get("force_group_send") is True
    assert user_receipt_calls[0]["metadata"].get("target_group_id") == "repair-room"
    assert str(user_receipt_calls[0]["body"]).startswith("已受理，工单 TCK-FAST-PRIVATE-001")

    private_calls: list[dict[str, Any]] = []
    for _ in range(20):
        private_calls = [
            item
            for item in runtime.gateway.outbound_calls
            if str(item.get("metadata", {}).get("outbound_type") or "") == "private_detail"
        ]
        if private_calls:
            break
        time.sleep(0.01)
    assert len(private_calls) == 1
    assert private_calls[0]["session_id"] == "dm:u_customer"
    assert "升级人工处理" in str(private_calls[0]["body"])


def test_process_wecom_message_group_fast_reply_suppresses_session_control_private_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECOM_GROUP_PRIVATE_DETAIL_ASYNC", "1")
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-room:user:u_customer",
                    "message_text": "/new",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text=(
                    "已切换到新问题模式，请描述你的新问题。"
                    "这是会话控制提示，不应作为私聊详细说明重复发送。"
                    "请直接在群里继续描述新的故障信息。"
                ),
                ticket_id="TCK-NO-PRIVATE-SESSION-CONTROL",
                ticket_action="new_issue_mode",
                queue="human-handoff",
                priority="P3",
            )
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-no-private-session-control-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer",
            "text": "/new",
            "req_id": "trace-no-private-session-control-1",
            "dispatch_targets": {"inbox:wecom.default": "group:ops-room"},
        },
    )

    assert result.status == "ok"
    user_receipt_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "user_receipt"
    ]
    assert user_receipt_calls
    assert user_receipt_calls[0]["metadata"].get("reply_mode") == "group_fast_rule"
    assert user_receipt_calls[0]["metadata"].get("private_detail_suppressed") is True

    private_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "private_detail"
    ]
    assert private_calls == []


def test_process_wecom_message_group_fast_reply_dedup_within_60_seconds() -> None:
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-dedup-room:user:u_customer",
                    "message_text": "请尽快安排处理",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text=(
                    "您好，已收到反馈并创建工单。"
                    "我们将尽快安排处理人员上门排查，同时持续同步进展，请留意消息。"
                    "为避免遗漏，请先保持电话畅通，现场工程师会在确认后第一时间联系您。"
                ),
                ticket_id="TCK-DEDUP-001",
                ticket_action="handoff",
                queue="human-handoff",
                priority="P2",
            )
        ),
    )

    payload = {
        "chatid": "repair-dedup-room",
        "chattype": "group",
        "sender_id": "u_customer",
        "text": "请尽快安排处理",
        "dispatch_targets": {"inbox:wecom.default": "group:ops-room:user:u_dispatch_bot"},
    }

    first_result = process_wecom_message(
        runtime,
        {
            **payload,
            "msgid": "mid-dedup-1",
            "req_id": "trace-dedup-1",
        },
    )
    second_result = process_wecom_message(
        runtime,
        {
            **payload,
            "msgid": "mid-dedup-2",
            "req_id": "trace-dedup-2",
        },
    )

    assert first_result.status == "ok"
    assert second_result.status == "ok"
    user_receipt_calls = [
        item
        for item in runtime.gateway.outbound_calls
        if str(item.get("metadata", {}).get("outbound_type") or "") == "user_receipt"
    ]
    assert len(user_receipt_calls) == 1
    assert user_receipt_calls[0]["metadata"].get("reply_mode") == "group_fast_rule"
    assert user_receipt_calls[0]["metadata"].get("target_group_id") == "repair-dedup-room"


def test_process_wecom_message_group_private_detail_binds_dm_ticket_context(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("WECOM_GROUP_PRIVATE_DETAIL_ASYNC", "1")
    ticket_api = _DummyTicketAPI()
    runtime = _DummyRuntime(
        gateway=_DummyGateway(
            {
                "status": "ok",
                "inbound": {
                    "channel": "wecom",
                    "session_id": "group:repair-room:user:u_customer",
                    "message_text": "请尽快安排处理",
                    "metadata": {"inbox": "wecom.default"},
                },
            }
        ),
        intake_workflow=_DummyIntakeWorkflow(
            _DummyIntakeResult(
                reply_text=(
                    "您好，收到您反馈的漏水问题。"
                    "我们已升级人工处理并安排处理人员跟进，后续将持续同步。"
                    "为确保定位准确，请补充具体楼层与区域，我们会尽快安排工程师上门。"
                ),
                ticket_id="TCK-FAST-BIND-001",
                ticket_action="handoff",
                queue="human-handoff",
                priority="P1",
            ),
            ticket_api=ticket_api,
        ),
    )

    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-fast-bind-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer",
            "text": "请尽快安排处理",
            "req_id": "trace-fast-bind-1",
            "dispatch_targets": {"inbox:wecom.default": "group:ops-room:user:u_dispatch_bot"},
        },
    )

    assert result.status == "ok"
    assert ticket_api.bind_calls
    assert ticket_api.bind_calls[0]["session_id"] == "dm:u_customer"
    assert ticket_api.bind_calls[0]["ticket_id"] == "TCK-FAST-BIND-001"
    assert ticket_api.bind_calls[0]["metadata"].get("source_session_id") == "group:repair-room:user:u_customer"
