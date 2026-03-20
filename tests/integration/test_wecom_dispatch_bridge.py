from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from scripts.run_acceptance import build_runtime
from scripts.wecom_bridge_server import process_wecom_message


@pytest.fixture(autouse=True)
def _disable_wecom_real_api(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WECOM_APP_API_ENABLED", "0")


class _BlockedDispatchAgent:
    def analyze(self, query_text: str, *, actor_id: str) -> dict[str, object]:
        _ = (query_text, actor_id)
        return {
            "advice_only": True,
            "answer": "dispatch blocked in runtime trace",
            "recommended_actions": [],
            "confidence": 0.71,
            "runtime_trace": {"policy_gate": {"enforced": True, "blocked_execution": True}},
        }


def _diverse_wecom_contents() -> list[str]:
    return [
        "空调不制冷，办公室 3A。",
        "会议室投影无法连接，请尽快处理。",
        "工位网络间歇性断开，影响线上会议。",
        "门禁刷卡无反应，前台无法进门。",
        "打印机卡纸并提示 E103 错误。",
        "茶水间漏水，地面有积水风险。",
        "电梯异响并伴随轻微抖动。",
        "机房温度过高，当前 34 度。",
        "显示器频繁黑屏，重启后复现。",
        "电话分机无法拨出外线。",
        "考勤机打卡记录不同步。",
        "财务电脑蓝屏，代码 0x0000007E。",
        "VPN 登录失败，提示 token invalid。",
        "邮件客户端收不到外部邮件。",
        "共享盘权限异常，无法访问项目目录。",
        "工单现在到哪一步了？",
        "有人在处理我的问题吗？",
        "预计什么时候修好？",
        "请同步一下当前进度。",
        "这个问题还在排队吗？",
        "我补充一下：故障从昨晚 11 点开始。",
        "补充：已重启设备 2 次，问题仍在。",
        "补充日志：error at module network_adapter.",
        "这个和上次同类型故障可能有关。",
        "优先级请调高，领导在催。",
        "/new 我还有一个新问题：工位灯不亮。",
        "/state 看一下当前会话状态。",
        "/end 先结束这次会话。",
        "new issue: parking gate sensor offline.",
        "state please",
        "请帮我转人工，谢谢。",
        "需要安排现场工程师上门。",
        "麻烦直接升级到值班主管。",
        "客户很急，请人工尽快介入。",
        "请安排跨组协同处理。",
        "这是地址：上海市浦东新区 XX 路 88 号 5 楼。",
        "联系电话 13800138000，随时可联系。",
        "资产编号 IT-DEV-2026-00991。",
        "设备序列号 SN-A1B2-C3D4-E5F6。",
        "报错截图链接：https://example.com/screenshot/123",
        "系统提示：{\"code\":\"E500\",\"message\":\"timeout\"}",
        "日志片段：WARN retry=3 latency=1200ms",
        "请按这个流程处理：1) 断电 2) 复位 3) 验证。",
        "问题描述如下：\n第一，无法登录。\n第二，验证码超时。",
        "我刚刚确认，问题已复现三次。",
        "这个问题和昨天那单是不是重复？",
        "请确认是否需要我这边配合测试。",
        "如果今天无法修复，请给临时方案。",
        "谢谢，辛苦了，麻烦持续同步进展。",
        "最后补充：影响范围是 A/B 两个区域共 30 人。",
    ]


def test_wecom_dispatch_bridge_auto_dispatch_success(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "wecom_dispatch_success.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    trace_id = "trace-dispatch-success"
    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-dispatch-success-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer_01",
            "text": "空调不制冷，办公室 3A。",
            "req_id": trace_id,
        },
    )

    assert result.status == "ok"
    assert result.ticket_id
    assert result.delivery_status == "dispatched"
    assert result.collab_target is not None
    assert result.collab_target["target_session_id"] == "group:ops-room:user:u_dispatch_bot"
    assert result.dispatch_decision is not None
    assert result.dispatch_decision["policy_gate"]["allowed"] is True

    events = runtime.trace_logger.query_by_trace(trace_id, limit=500)
    assert any(item["event_type"] == "wecom_dispatch_decision" for item in events)
    assert any(item["event_type"] == "wecom_dispatch_delivery" for item in events)
    assert any(
        item["event_type"] == "egress_rendered"
        and item.get("session_id") == "group:ops-room:user:u_dispatch_bot"
        for item in events
    )
    assert any(
        item["event_type"] == "wecom_private_detail_async_scheduled"
        and item.get("session_id") == "dm:u_customer_01"
        for item in events
    )
    collab_egress_events = [
        item
        for item in events
        if item.get("event_type") == "egress_rendered"
        and item.get("session_id") == "group:ops-room:user:u_dispatch_bot"
        and str(item.get("ticket_id") or "") == str(result.ticket_id or "")
        and str(
            (
                (
                    (item.get("payload") or {}).get("payload") or {}
                ).get("metadata")
                or {}
            ).get("outbound_type")
            or ""
        )
        == "collab_dispatch"
    ]
    ordered_collab_chunks = sorted(
        collab_egress_events,
        key=lambda item: int(
            (
                (
                    (item.get("payload") or {}).get("payload") or {}
                ).get("metadata")
                or {}
            ).get("chunk_index")
            or 1
        ),
    )
    collab_content = "".join(
        str(
            (
                (
                    (item.get("payload") or {}).get("payload") or {}
                ).get("text")
                or {}
            ).get("content")
            or ""
        )
        for item in ordered_collab_chunks
    )
    assert f"新工单 {result.ticket_id} 已创建" in collab_content
    assert "工单详情：" in collab_content
    assert "[new-ticket]" not in collab_content
    assert "commands:" not in collab_content


def test_wecom_dispatch_bridge_system_mapping_writes_trace_and_metadata(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "wecom_dispatch_system_mapping_trace.db")
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "system:procurement": "group:proc-room:user:u_dispatch_bot",
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
                "default": "group:default-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    trace_id = "trace-dispatch-system-mapping-1"
    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-dispatch-system-mapping-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer_03",
            "text": "请帮我创建采购申请",
            "req_id": trace_id,
        },
    )

    assert result.status == "ok"
    assert result.delivery_status == "dispatched"
    assert result.collab_target is not None
    assert result.collab_target["source"] == "mapping:system:procurement"
    assert result.collab_target["matched_key"] == "system:procurement"
    assert result.dispatch_decision is not None
    assert result.dispatch_decision["route"]["system"] == "procurement"
    assert result.dispatch_decision["route"]["matched_key"] == "system:procurement"

    events = runtime.trace_logger.query_by_trace(trace_id, limit=500)
    decision_events = [item for item in events if item.get("event_type") == "wecom_dispatch_decision"]
    assert decision_events
    assert decision_events[-1]["payload"]["system"] == "procurement"
    assert decision_events[-1]["payload"]["matched_key"] == "system:procurement"

    collab_egress_events = [
        item
        for item in events
        if item.get("event_type") == "egress_rendered"
        and item.get("session_id") == "group:proc-room:user:u_dispatch_bot"
        and str(
            (
                (
                    (item.get("payload") or {}).get("payload") or {}
                ).get("metadata")
                or {}
            ).get("outbound_type")
            or ""
        )
        == "collab_dispatch"
    ]
    assert collab_egress_events
    collab_metadata = (
        ((collab_egress_events[-1].get("payload") or {}).get("payload") or {}).get("metadata") or {}
    )
    assert collab_metadata.get("system") == "procurement"
    assert collab_metadata.get("dispatch_matched_key") == "system:procurement"


def test_wecom_dispatch_bridge_is_blocked_when_target_mapping_missing(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "wecom_dispatch_blocked.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv("WECOM_DISPATCH_TARGETS_JSON", "")
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    trace_id = f"trace-dispatch-blocked-{tmp_path.name}"
    payload = {
        "msgid": "mid-dispatch-blocked-1",
        "chatid": "repair-room",
        "chattype": "group",
        "sender_id": "u_customer_02",
        "text": "会议室投影无法连接。",
        "req_id": trace_id,
    }
    result = process_wecom_message(runtime, payload)

    assert result.status == "ok"
    assert result.ticket_id
    assert result.delivery_status == "blocked_by_policy_gate"
    assert result.dispatch_decision is not None
    assert result.dispatch_decision["policy_gate"]["allowed"] is False
    assert result.dispatch_decision["policy_gate"]["reason"] == "no_target_mapping"

    source_session_id = "group:repair-room:user:u_customer_02"
    events = runtime.trace_logger.query_by_trace(trace_id, limit=500)
    assert any(item["event_type"] == "wecom_dispatch_blocked" for item in events)
    egress_events = [item for item in events if item.get("event_type") == "egress_rendered"]
    assert egress_events
    assert any(str(item.get("session_id") or "") == source_session_id for item in egress_events)
    assert not any(
        str(
            (
                (
                    (item.get("payload") or {}).get("payload") or {}
                ).get("metadata")
                or {}
            ).get("outbound_type")
            or ""
        )
        == "collab_dispatch"
        for item in egress_events
    )


def test_wecom_dispatch_bridge_collab_push_bypasses_dispatch_policy_block(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "wecom_dispatch_collab_push.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    object.__setattr__(runtime, "dispatch_agent", _BlockedDispatchAgent())
    trace_id = "trace-collab-push-bypass"
    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-collab-push-bypass-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer_collab_push",
            "text": "d栋厕所漏水",
            "req_id": trace_id,
        },
    )

    assert result.status == "ok"
    assert result.ticket_id
    assert result.delivery_status == "dispatched"
    assert result.dispatch_decision is not None
    assert result.dispatch_decision["policy_gate"]["allowed"] is True
    assert result.dispatch_decision["policy_gate"]["blocked_execution"] is False

    events = runtime.trace_logger.query_by_trace(trace_id, limit=500)
    assert any(item["event_type"] == "wecom_dispatch_delivery" for item in events)
    assert any(
        item["event_type"] == "egress_rendered"
        and item.get("session_id") == "group:ops-room:user:u_dispatch_bot"
        for item in events
    )


def test_wecom_dispatch_bridge_accepts_plain_group_id_target_mapping(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "wecom_dispatch_plain_group_target.db")
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "ops-room",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    trace_id = "trace-dispatch-plain-group-target"
    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-dispatch-plain-group-target-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer_plain_group",
            "text": "弱电间有焦糊味，请尽快处理。",
            "req_id": trace_id,
        },
    )

    assert result.status == "ok"
    assert result.ticket_id
    assert result.delivery_status == "dispatched"
    assert result.collab_target is not None
    assert result.collab_target["target_session_id"] == "group:ops-room:user:u_dispatch_bot"
    assert result.dispatch_decision is not None
    assert result.dispatch_decision["policy_gate"]["allowed"] is True

    events = runtime.trace_logger.query_by_trace(trace_id, limit=500)
    assert any(
        item["event_type"] == "egress_rendered"
        and item.get("session_id") == "group:ops-room:user:u_dispatch_bot"
        for item in events
    )


def test_wecom_dispatch_bridge_accepts_50_diverse_contents(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "wecom_dispatch_matrix.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    texts = _diverse_wecom_contents()
    assert len(texts) == 50

    allowed_reasons = {
        "allowed",
        "auto_dispatch_disabled",
        "dispatch_agent_policy_blocked",
        "ticket_action_not_dispatchable",
        "no_target_mapping",
    }
    allowed_delivery_status = {
        "dispatched",
        "blocked_by_policy_gate",
        "dispatch_missing_payload",
        "dispatch_unsupported",
        "not_dispatched",
    }

    for idx, text in enumerate(texts, start=1):
        trace_id = f"trace-dispatch-matrix-{idx:02d}"
        result = process_wecom_message(
            runtime,
            {
                "msgid": f"mid-dispatch-matrix-{idx:02d}",
                "chatid": "repair-room",
                "chattype": "group",
                "sender_id": f"u_customer_matrix_{idx % 5}",
                "text": text,
                "req_id": trace_id,
            },
        )

        assert result.handled is True, f"case={idx} not handled"
        assert result.status == "ok", f"case={idx} status={result.status}"
        assert isinstance(result.reply_text, str), f"case={idx} invalid reply_text"
        assert result.reply_text.strip(), f"case={idx} empty reply_text"
        assert result.ticket_id, f"case={idx} missing ticket_id"
        assert isinstance(result.channel_route, dict), f"case={idx} channel_route missing"
        assert isinstance(result.dispatch_decision, dict), f"case={idx} dispatch_decision missing"
        assert result.delivery_status in allowed_delivery_status, (
            f"case={idx} unexpected delivery_status={result.delivery_status}"
        )

        policy_gate = result.dispatch_decision.get("policy_gate")
        assert isinstance(policy_gate, dict), f"case={idx} policy_gate missing"
        reason = str(policy_gate.get("reason") or "")
        assert reason in allowed_reasons, f"case={idx} unexpected policy reason={reason}"
        if result.delivery_status == "dispatched":
            assert policy_gate.get("allowed") is True, f"case={idx} dispatched but gate not allowed"

        events = runtime.trace_logger.query_by_trace(trace_id, limit=200)
        assert any(item.get("event_type") == "wecom_dispatch_decision" for item in events), (
            f"case={idx} missing dispatch decision trace"
        )
        assert any(item.get("event_type") == "wecom_dispatch_delivery" for item in events), (
            f"case={idx} missing dispatch delivery trace"
        )


def test_wecom_dispatch_bridge_collab_command_variants_sync_back_to_repair_group(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH",
        str(tmp_path / "wecom_dispatch_collab_variants.db"),
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    created = process_wecom_message(
        runtime,
        {
            "msgid": "mid-collab-variant-create-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer_variant_01",
            "text": "电梯异响，伴随轻微抖动。",
            "req_id": "trace-collab-variant-create-1",
        },
    )
    assert created.status == "ok"
    assert created.ticket_id

    claim_slash_space = process_wecom_message(
        runtime,
        {
            "msgid": "mid-collab-variant-claim-1",
            "chatid": "ops-room",
            "chattype": "group",
            "sender_id": "u_ops_variant_01",
            "text": f"/ claim {created.ticket_id}",
            "req_id": "trace-collab-variant-claim-1",
        },
    )
    assert claim_slash_space.status == "ok"
    assert claim_slash_space.ticket_action == "collab_claim"
    assert claim_slash_space.delivery_status == "dispatched"
    assert claim_slash_space.collab_target is not None
    assert (
        claim_slash_space.collab_target["target_session_id"]
        == "group:repair-room:user:u_customer_variant_01"
    )
    assert claim_slash_space.collab_target["source"] == "workflow_cross_group_sync"

    claim_natural = process_wecom_message(
        runtime,
        {
            "msgid": "mid-collab-variant-claim-2",
            "chatid": "ops-room",
            "chattype": "group",
            "sender_id": "u_ops_variant_02",
            "text": f"认领工单 {created.ticket_id}",
            "req_id": "trace-collab-variant-claim-2",
        },
    )
    assert claim_natural.status == "ok"
    assert claim_natural.ticket_action == "collab_claim"
    assert claim_natural.delivery_status == "dispatched"

    events = runtime.trace_logger.query_by_trace("trace-collab-variant-claim-2", limit=300)
    assert any(item.get("event_type") == "wecom_dispatch_delivery" for item in events)
    assert any(
        item.get("event_type") == "egress_rendered"
        and item.get("session_id") == "group:repair-room:user:u_customer_variant_01"
        for item in events
    )


def test_wecom_dispatch_bridge_group_fast_reply_binds_dm_session_context(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH",
        str(tmp_path / "wecom_dispatch_dm_bind.db"),
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv("WECOM_GROUP_PRIVATE_DETAIL_ASYNC", "1")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    trace_id = "trace-group-fast-dm-bind-1"
    result = process_wecom_message(
        runtime,
        {
            "msgid": "mid-group-fast-dm-bind-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer_dm_bind",
            "text": (
                "空调不制冷，办公室 3A。"
                "温度持续升高，已影响会议进行，请尽快安排处理并同步进展。"
            ),
            "req_id": trace_id,
        },
    )

    assert result.status == "ok"
    assert result.ticket_id
    ticket_api = getattr(runtime.intake_workflow, "_ticket_api", None)
    assert ticket_api is not None
    dm_context = ticket_api.get_session_context("dm:u_customer_dm_bind")
    assert isinstance(dm_context, dict)
    assert str(dm_context.get("active_ticket_id") or "") == result.ticket_id

    events = runtime.trace_logger.query_by_trace(trace_id, limit=500)
    assert any(item.get("event_type") == "wecom_private_detail_session_bound" for item in events)


def test_wecom_dispatch_bridge_dm_supplement_syncs_to_collab_group(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH",
        str(tmp_path / "wecom_dispatch_dm_supplement_sync.db"),
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    created = process_wecom_message(
        runtime,
        {
            "msgid": "mid-dm-supplement-create-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": "u_customer_dm_supplement",
            "text": "D栋厕所漏水，水已经流到走廊。",
            "req_id": "trace-dm-supplement-create-1",
        },
    )
    assert created.status == "ok"
    assert created.ticket_id

    ticket_api = getattr(runtime.intake_workflow, "_ticket_api", None)
    assert ticket_api is not None
    ticket_api.bind_session_ticket(
        "dm:u_customer_dm_supplement",
        created.ticket_id,
        metadata={"source": "integration_test"},
    )

    supplement_trace_id = "trace-dm-supplement-sync-1"
    supplemented = process_wecom_message(
        runtime,
        {
            "msgid": "mid-dm-supplement-sync-1",
            "chattype": "single",
            "sender_id": "u_customer_dm_supplement",
            "text": "补充：具体在三楼B区男厕门口，持续渗水约30分钟。",
            "req_id": supplement_trace_id,
        },
    )
    assert supplemented.status == "ok"
    assert supplemented.delivery_status == "dispatched"

    events = runtime.trace_logger.query_by_trace(supplement_trace_id, limit=500)
    collab_egress_events = [
        item
        for item in events
        if item.get("event_type") == "egress_rendered"
        and item.get("session_id") == "group:ops-room:user:u_dispatch_bot"
        and str(
            (((item.get("payload") or {}).get("payload") or {}).get("metadata") or {}).get(
                "outbound_type"
            )
            or ""
        )
        == "collab_dispatch"
    ]
    assert collab_egress_events
    ordered_collab_chunks = sorted(
        collab_egress_events,
        key=lambda item: int(
            (((item.get("payload") or {}).get("payload") or {}).get("metadata") or {}
        ).get("chunk_index")
        or 1,
        ),
    )
    collab_content = "".join(
        str((((item.get("payload") or {}).get("payload") or {}).get("text") or {}).get("content") or "")
        for item in ordered_collab_chunks
    )
    assert f"工单 {created.ticket_id} 收到补充信息：" in collab_content
    assert "三楼B区男厕门口" in collab_content


def test_wecom_dispatch_bridge_private_chat_supports_fault_report_and_progress_query(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH",
        str(tmp_path / "wecom_dispatch_private_report_progress.db"),
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:u_dispatch_bot",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    sender_id = "u_private_report_progress_01"
    report_trace_id = "trace-private-report-1"
    reported = process_wecom_message(
        runtime,
        {
            "msgid": "mid-private-report-1",
            "chattype": "single",
            "sender_id": sender_id,
            "text": "D栋厕所漏水，位置在三楼B区男厕门口，持续渗水。",
            "req_id": report_trace_id,
        },
    )
    assert reported.status == "ok"
    assert reported.ticket_id
    assert reported.ticket_action in {"create_ticket", "handoff", "conservative_ticket"}
    assert reported.reply_text.strip()

    progress_trace_id = "trace-private-progress-1"
    progressed = process_wecom_message(
        runtime,
        {
            "msgid": "mid-private-progress-1",
            "chattype": "single",
            "sender_id": sender_id,
            "text": "工单现在到哪一步了？",
            "req_id": progress_trace_id,
        },
    )
    assert progressed.status == "ok"
    assert progressed.ticket_id == reported.ticket_id
    assert progressed.ticket_action == "progress_reply"
    assert progressed.reply_text.strip()

    report_events = runtime.trace_logger.query_by_trace(report_trace_id, limit=500)
    progress_events = runtime.trace_logger.query_by_trace(progress_trace_id, limit=500)
    assert any(
        item.get("event_type") == "egress_rendered"
        and item.get("session_id") == f"dm:{sender_id}"
        for item in report_events
    )
    assert any(
        item.get("event_type") == "egress_rendered"
        and item.get("session_id") == f"dm:{sender_id}"
        for item in progress_events
    )

    def _contains_private_detail(events: list[dict[str, object]]) -> bool:
        for item in events:
            if item.get("event_type") != "egress_rendered":
                continue
            metadata = (
                (
                    (item.get("payload") or {}).get("payload") or {}
                ).get("metadata")
                or {}
            )
            if str(metadata.get("outbound_type") or "") == "private_detail":
                return True
        return False

    assert _contains_private_detail(report_events) is False
    assert _contains_private_detail(progress_events) is False


def test_wecom_dispatch_bridge_real_users_customer_operator_full_chain(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH",
        str(tmp_path / "wecom_dispatch_real_users_chain.db"),
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv(
        "WECOM_DISPATCH_TARGETS_JSON",
        json.dumps(
            {
                "inbox:wecom.default": "group:ops-room:user:Yusongze",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("WECOM_DISPATCH_AUTO_ENABLED", "1")

    runtime = build_runtime("dev")
    customer_id = "keguonian"
    operator_id = "Yusongze"

    created = process_wecom_message(
        runtime,
        {
            "msgid": "mid-real-users-create-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": customer_id,
            "text": "空调不制冷，会议室温度持续升高，请尽快处理。",
            "req_id": "trace-real-users-create-1",
        },
    )
    assert created.status == "ok"
    assert created.ticket_id
    assert created.delivery_status == "dispatched"
    assert created.collab_target is not None
    assert created.collab_target["target_session_id"] == "group:ops-room:user:Yusongze"

    claimed = process_wecom_message(
        runtime,
        {
            "msgid": "mid-real-users-claim-1",
            "chatid": "ops-room",
            "chattype": "group",
            "sender_id": operator_id,
            "text": f"/claim {created.ticket_id}",
            "req_id": "trace-real-users-claim-1",
        },
    )
    assert claimed.status == "ok"
    assert claimed.ticket_action == "collab_claim"
    assert claimed.delivery_status == "dispatched"
    assert claimed.collab_target is not None
    assert claimed.collab_target["source"] == "workflow_cross_group_sync"
    assert claimed.collab_target["target_session_id"] == f"group:repair-room:user:{customer_id}"

    resolved = process_wecom_message(
        runtime,
        {
            "msgid": "mid-real-users-resolve-1",
            "chatid": "ops-room",
            "chattype": "group",
            "sender_id": operator_id,
            "text": f"/resolve {created.ticket_id} 已完成现场处理并恢复。",
            "req_id": "trace-real-users-resolve-1",
        },
    )
    assert resolved.status == "ok"
    assert resolved.ticket_action == "collab_resolve"

    confirmed = process_wecom_message(
        runtime,
        {
            "msgid": "mid-real-users-confirm-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": customer_id,
            "text": "确认已解决，谢谢。",
            "req_id": "trace-real-users-confirm-1",
        },
    )
    assert confirmed.status == "ok"
    assert confirmed.ticket_action == "collab_customer_confirm"

    ticket_api = getattr(runtime.intake_workflow, "_ticket_api", None)
    assert ticket_api is not None
    closed_ticket = ticket_api.require_ticket(str(created.ticket_id))
    assert closed_ticket.status == "closed"

    followup = process_wecom_message(
        runtime,
        {
            "msgid": "mid-real-users-followup-1",
            "chatid": "repair-room",
            "chattype": "group",
            "sender_id": customer_id,
            "text": "最后补充：影响范围是 A/B 两个区域共 30 人。",
            "req_id": "trace-real-users-followup-1",
        },
    )
    assert followup.status == "ok"
    assert followup.ticket_id
    assert followup.ticket_id != created.ticket_id
