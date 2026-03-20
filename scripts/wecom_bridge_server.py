from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from app.agents.deep.operator_dispatch_agent import build_dispatch_collaboration_agent
from scripts.dev_reloader import (
    RELOADER_CHILD_ENV,
    build_default_watch_roots,
    run_with_reloader,
)
from scripts.run_acceptance import build_runtime
from storage.models import InboundEnvelope

DEFAULT_REPLY_ON_ERROR = "系统繁忙，请稍后再试。"
DEFAULT_BRIDGE_PATH = "/wecom/process"
DEFAULT_DISPATCH_TARGETS_ENV = "WECOM_DISPATCH_TARGETS_JSON"
DEFAULT_DISPATCH_AUTO_ENV = "WECOM_DISPATCH_AUTO_ENABLED"
DEFAULT_DISPATCH_GROUP_ACTOR = "u_dispatch_bot"
DEFAULT_WECOM_OUTBOUND_CHUNK_CHARS_ENV = "WECOM_BRIDGE_OUTBOUND_CHUNK_CHARS"
DEFAULT_WECOM_OUTBOUND_CHUNK_CHARS = 1200
DEFAULT_GROUP_FAST_REPLY_MIN_CHARS = 60
DEFAULT_PRIVATE_DETAIL_ASYNC_ENV = "WECOM_GROUP_PRIVATE_DETAIL_ASYNC"
DEFAULT_PRIVATE_DETAIL_RETRY_ATTEMPTS_ENV = "WECOM_GROUP_PRIVATE_DETAIL_RETRY_ATTEMPTS"
DEFAULT_PRIVATE_DETAIL_RETRY_DELAY_MS_ENV = "WECOM_GROUP_PRIVATE_DETAIL_RETRY_DELAY_MS"
DEFAULT_PRIVATE_DETAIL_RETRY_ATTEMPTS = 3
DEFAULT_PRIVATE_DETAIL_RETRY_DELAY_MS = 300
DEFAULT_GROUP_TEMPLATE_DEDUP_WINDOW_SECONDS_ENV = "WECOM_GROUP_TEMPLATE_DEDUP_WINDOW_SECONDS"
DEFAULT_GROUP_TEMPLATE_DEDUP_WINDOW_SECONDS = 60
_PRIORITY_LABELS_ZH: dict[str, str] = {
    "P0": "紧急",
    "P1": "高",
    "P2": "中",
    "P3": "普通",
    "P4": "低",
}
_GROUP_TEMPLATE_DEDUP_CACHE: dict[tuple[str, str, str], float] = {}
_GROUP_TEMPLATE_DEDUP_LOCK = threading.Lock()
_MACHINE_DETAIL_MARKERS: tuple[str, ...] = (
    "[new-ticket]",
    "summary=",
    "sla_remaining=",
    "risk=",
    "similar=",
    "commands:",
)
_PRIVATE_DETAIL_SUPPRESS_PHRASES: tuple[str, ...] = (
    "已切换到新问题模式",
    "请描述你的新问题",
    "已按新会话处理，并创建/关联新工单上下文",
    "当前会话已结束",
    "本次会话已结束",
)


@dataclass(frozen=True)
class BridgeResult:
    handled: bool
    reply_text: str
    status: str
    ticket_id: str | None = None
    ticket_action: str | None = None
    channel_route: dict[str, Any] | None = None
    collab_target: dict[str, Any] | None = None
    dispatch_decision: dict[str, Any] | None = None
    delivery_status: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "handled": self.handled,
            "reply_text": self.reply_text,
            "status": self.status,
            "ticket_id": self.ticket_id,
            "ticket_action": self.ticket_action,
            "channel_route": self.channel_route,
            "collab_target": self.collab_target,
            "dispatch_decision": self.dispatch_decision,
            "delivery_status": self.delivery_status,
        }


class _GatewayLike(Protocol):
    def receive(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class _IntakeLike(Protocol):
    def run(self, envelope: InboundEnvelope, *, existing_ticket_id: str | None = None) -> Any: ...


class _RuntimeLike(Protocol):
    @property
    def gateway(self) -> _GatewayLike: ...

    @property
    def intake_workflow(self) -> _IntakeLike: ...


def process_wecom_message(runtime: _RuntimeLike, payload: dict[str, Any]) -> BridgeResult:
    text = _pick_text(payload)
    sender_id = _pick_string(
        payload,
        "sender_id",
        "sender_id.user_id",
        "sender_id.userid",
        "from_userid",
        "from_user_id",
        "fromUserId",
        "FromUserName",
        "from.userid",
        "from.id",
        "from.user_id",
        "sender.userid",
        "sender.user_id",
        "sender.id",
        "sender.sender_id.user_id",
        "sender.sender_id.userid",
        "sender.sender_id.userId",
        "userid",
        "user_id",
        "UserID",
    )
    chat_id = (
        _pick_string(
            payload,
            "chatid",
            "chat_id",
            "chatId",
            "conversationid",
            "ChatId",
            "conversation_id",
            "conversation.id",
            "chat_info.id",
            "chat.id",
        )
        or sender_id
    )
    chat_type = (
        _pick_string(payload, "chattype", "ChatType", "chat_type", "conversation_type") or "single"
    ).lower()
    raw_msg_id = _pick_string(
        payload,
        "msgid",
        "MsgId",
        "message_id",
        "message.msgid",
        "message.msg_id",
        "msg.msgid",
        "msg.msg_id",
    )
    req_id = (
        _pick_string(payload, "req_id", "ReqId", "trace_id")
        or raw_msg_id
        or f"trace-{time.time_ns()}"
    )
    msg_id = raw_msg_id or _build_fallback_msg_id(payload=payload, req_id=req_id)

    if not text:
        return BridgeResult(handled=True, reply_text="", status="ignored_empty")

    if not sender_id:
        return BridgeResult(
            handled=True,
            reply_text=DEFAULT_REPLY_ON_ERROR,
            status="invalid_sender",
        )

    session_id = _compose_session_id(sender_id=sender_id, chat_id=chat_id, chat_type=chat_type)
    ingress_payload = {
        "trace_id": req_id,
        "source": "wecom_bridge",
        "session_id": session_id,
        "FromUserName": sender_id,
        "Content": text,
        "MsgId": msg_id,
        "CreateTime": str(int(time.time())),
        "inbox": "wecom.default",
    }
    ingress_result = runtime.gateway.receive("wecom", ingress_payload)
    ingress_status = str(ingress_result.get("status") or "error")
    if ingress_status == "duplicate_ignored":
        return BridgeResult(handled=True, reply_text="", status=ingress_status)
    if ingress_status != "ok":
        return BridgeResult(handled=True, reply_text=DEFAULT_REPLY_ON_ERROR, status=ingress_status)

    inbound_payload = ingress_result.get("inbound")
    if not isinstance(inbound_payload, dict):
        return BridgeResult(
            handled=True,
            reply_text=DEFAULT_REPLY_ON_ERROR,
            status="invalid_inbound",
        )

    envelope = InboundEnvelope(
        channel=str(inbound_payload.get("channel") or "wecom"),
        session_id=str(inbound_payload.get("session_id") or session_id),
        message_text=str(inbound_payload.get("message_text") or text),
        metadata=dict(inbound_payload.get("metadata") or {}),
    )
    existing_ticket_id = str(envelope.metadata.get("ticket_id") or "").strip() or None
    has_existing_ticket_context = existing_ticket_id is not None
    intake = runtime.intake_workflow.run(envelope, existing_ticket_id=existing_ticket_id)
    ticket_id = str(getattr(intake, "ticket_id", "") or "").strip() or None
    ticket_action = str(getattr(intake, "ticket_action", "") or "").strip() or None
    queue = str(getattr(intake, "queue", "") or "").strip()
    priority = str(getattr(intake, "priority", "") or "").strip()
    collab_push = getattr(intake, "collab_push", None)
    inbox = str(envelope.metadata.get("inbox") or "wecom.default").strip()
    system_key = str(
        getattr(intake, "system", "")
        or getattr(intake, "system_key", "")
        or envelope.metadata.get("system")
        or envelope.metadata.get("system_key")
        or ""
    ).strip().lower()
    reply_text = str(getattr(intake, "reply_text", "") or "")
    user_receipt_body = reply_text
    private_detail_body = ""
    user_receipt_session_id = envelope.session_id
    user_receipt_metadata: dict[str, Any] = {}

    group_fast_reply = _build_group_fast_reply(
        chat_type=chat_type,
        ticket_action=ticket_action,
        ticket_id=ticket_id,
        priority=priority,
        reply_text=reply_text,
    )
    if group_fast_reply is not None:
        group_id = _safe_group_id(chat_id=chat_id, session_id=envelope.session_id)
        if group_id:
            user_receipt_body = group_fast_reply
            user_receipt_metadata["force_group_send"] = True
            user_receipt_metadata["target_group_id"] = group_id
            user_receipt_metadata["reply_mode"] = "group_fast_rule"
            if _should_send_private_detail(ticket_action=ticket_action, reply_text=reply_text):
                private_detail_body = reply_text.strip()
            else:
                user_receipt_metadata["private_detail_suppressed"] = True
        else:
            user_receipt_metadata["reply_mode"] = "group_fast_rule_skipped_no_group_id"

    dispatch_decision = _build_dispatch_decision(
        runtime=runtime,
        query_text=(
            f"dispatch ticket={ticket_id or 'unknown'} "
            f"system={system_key or 'unknown'} queue={queue} inbox={inbox}"
        ),
        queue=queue,
    )
    collab_target = _resolve_collab_target(
        payload=payload,
        system_key=system_key,
        queue=queue,
        inbox=inbox,
        collab_push=collab_push if isinstance(collab_push, dict) else None,
    )
    policy_gate = _evaluate_dispatch_policy_gate(
        ticket_action=ticket_action,
        target_session_id=str(collab_target.get("target_session_id") or "").strip(),
        dispatch_runtime_trace=dispatch_decision.get("runtime_trace"),
        has_collab_push=(
            isinstance(collab_push, dict) and bool(str(collab_push.get("message") or "").strip())
        ),
        has_existing_ticket_context=has_existing_ticket_context,
    )
    dispatch_decision["policy_gate"] = policy_gate
    dispatch_decision["route"] = {
        "system": system_key,
        "queue": queue,
        "inbox": inbox,
        "matched_key": collab_target.get("matched_key"),
        "target_session_id": collab_target.get("target_session_id"),
        "target_group_id": collab_target.get("target_group_id"),
        "source": collab_target.get("source"),
    }

    _trace_dispatch_event(
        runtime,
        event_type="wecom_dispatch_decision",
        trace_id=req_id,
        ticket_id=ticket_id,
        session_id=envelope.session_id,
        payload={
            "system": system_key,
            "matched_key": collab_target.get("matched_key"),
            "ticket_action": ticket_action,
            "decision": dispatch_decision,
            "collab_target": collab_target,
        },
    )

    _send_outbound_if_supported(
        runtime,
        channel=str(envelope.channel or "wecom"),
        session_id=user_receipt_session_id,
        body=user_receipt_body,
        metadata={
            "trace_id": req_id,
            "ticket_id": ticket_id,
            "outbound_type": "user_receipt",
            "system": system_key,
            "dispatch_matched_key": collab_target.get("matched_key"),
            **user_receipt_metadata,
        },
    )
    if private_detail_body:
        _bind_private_detail_ticket_context(
            runtime=runtime,
            session_id=f"dm:{sender_id}",
            ticket_id=ticket_id,
            source_session_id=envelope.session_id,
            trace_id=req_id,
        )
        _send_private_detail(
            runtime=runtime,
            channel=str(envelope.channel or "wecom"),
            session_id=f"dm:{sender_id}",
            body=private_detail_body,
            metadata={
                "trace_id": req_id,
                "ticket_id": ticket_id,
                "outbound_type": "private_detail",
                "system": system_key,
                "dispatch_matched_key": collab_target.get("matched_key"),
                "reply_mode": "group_fast_private_detail",
                "source_session_id": envelope.session_id,
            },
        )

    delivery_status = "not_dispatched"
    if bool(policy_gate.get("allowed")):
        collab_message = _resolve_collab_message(
            ticket_id=ticket_id,
            queue=queue,
            priority=priority,
            ticket_action=ticket_action,
            dispatch_decision=dispatch_decision,
            collab_push=collab_push if isinstance(collab_push, dict) else None,
            source_message_text=str(envelope.message_text or ""),
            has_existing_ticket_context=has_existing_ticket_context,
        )
        target_session_id = str(collab_target.get("target_session_id") or "").strip()
        if collab_message and target_session_id:
            sent = _send_outbound_if_supported(
                runtime,
                channel=str(envelope.channel or "wecom"),
                session_id=target_session_id,
                body=collab_message,
                metadata={
                    "trace_id": req_id,
                    "ticket_id": ticket_id,
                    "outbound_type": "collab_dispatch",
                    "system": system_key,
                    "dispatch_reason": str(policy_gate.get("reason") or ""),
                    "dispatch_matched_key": collab_target.get("matched_key"),
                    "dispatch_target": target_session_id,
                    "target_group_id": collab_target.get("target_group_id"),
                },
            )
            delivery_status = "dispatched" if sent else "dispatch_unsupported"
        else:
            delivery_status = "dispatch_missing_payload"
    else:
        delivery_status = "blocked_by_policy_gate"
        _trace_dispatch_event(
            runtime,
            event_type="wecom_dispatch_blocked",
            trace_id=req_id,
            ticket_id=ticket_id,
            session_id=envelope.session_id,
            payload={
                "system": system_key,
                "matched_key": collab_target.get("matched_key"),
                "reason": policy_gate.get("reason"),
                "ticket_action": ticket_action,
                "target_session_id": collab_target.get("target_session_id"),
            },
        )

    channel_route = {
        "inbound": str(envelope.channel or "wecom"),
        "source_session_id": envelope.session_id,
        "collab_target": collab_target,
        "dispatch_decision": dispatch_decision,
        "delivery_status": delivery_status,
    }

    _trace_dispatch_event(
        runtime,
        event_type="wecom_dispatch_delivery",
        trace_id=req_id,
        ticket_id=ticket_id,
        session_id=envelope.session_id,
        payload={
            "system": system_key,
            "matched_key": collab_target.get("matched_key"),
            "delivery_status": delivery_status,
            "channel_route": channel_route,
        },
    )

    return BridgeResult(
        handled=True,
        reply_text=user_receipt_body,
        status="ok",
        ticket_id=ticket_id,
        ticket_action=ticket_action,
        channel_route=channel_route,
        collab_target=collab_target,
        dispatch_decision=dispatch_decision,
        delivery_status=delivery_status,
    )


def _build_dispatch_decision(
    *,
    runtime: _RuntimeLike,
    query_text: str,
    queue: str,
) -> dict[str, Any]:
    dispatch_agent = getattr(runtime, "dispatch_agent", None)
    if dispatch_agent is None:
        dispatch_agent = build_dispatch_collaboration_agent(
            read_queue_summary_tool=lambda: [
                {
                    "queue_name": queue or "support",
                    "open_count": 1,
                    "in_progress_count": 1,
                    "warning_count": 0,
                    "breached_count": 0,
                    "escalated_count": 0,
                    "assignee_count": 1,
                }
            ],
            search_grounding_tool=lambda query: [],
        )
    decision = dispatch_agent.analyze(query_text, actor_id="wecom-bridge")
    return {
        "advice_only": bool(decision.get("advice_only", True)),
        "answer": str(decision.get("answer") or ""),
        "recommended_actions": list(decision.get("recommended_actions") or []),
        "confidence": float(decision.get("confidence") or 0.0),
        "runtime_trace": dict(decision.get("runtime_trace") or {}),
    }


def _resolve_collab_target(
    *,
    payload: dict[str, Any],
    system_key: str,
    queue: str,
    inbox: str,
    collab_push: dict[str, Any] | None,
) -> dict[str, Any]:
    if collab_push is not None:
        explicit_session_id = str(collab_push.get("session_id") or "").strip()
        if explicit_session_id:
            return {
                "source": "workflow_cross_group_sync",
                "matched_key": "workflow_cross_group_sync",
                "target_session_id": explicit_session_id,
                "target_group_id": _group_id_from_session_id(explicit_session_id),
            }
    mapping = _load_dispatch_targets(payload)
    for key in (
        f"system:{system_key}",
        system_key,
        f"queue:{queue}",
        f"inbox:{inbox}",
        queue,
        inbox,
        "default",
    ):
        if not key:
            continue
        target = _coerce_target(mapping.get(key))
        if target is None:
            continue
        return {
            "source": f"mapping:{key}",
            "matched_key": key,
            "target_session_id": target["target_session_id"],
            "target_group_id": target.get("target_group_id"),
        }
    return {
        "source": "mapping:none",
        "matched_key": None,
        "target_session_id": None,
        "target_group_id": None,
    }


def _load_dispatch_targets(payload: dict[str, Any]) -> dict[str, Any]:
    raw_targets = payload.get("dispatch_targets")
    if isinstance(raw_targets, dict):
        return dict(raw_targets)
    raw_env = os.getenv(DEFAULT_DISPATCH_TARGETS_ENV, "").strip()
    if not raw_env:
        return {}
    try:
        parsed = json.loads(raw_env)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _coerce_target(raw: Any) -> dict[str, str] | None:
    if isinstance(raw, str):
        session_id = raw.strip()
        if not session_id:
            return None
        if session_id.startswith("group:") and ":user:" not in session_id:
            group_id = session_id.split(":", 1)[-1].strip()
            if not group_id:
                return None
            session_id = f"group:{group_id}:user:{DEFAULT_DISPATCH_GROUP_ACTOR}"
        elif ":" not in session_id:
            group_id = session_id
            session_id = f"group:{group_id}:user:{DEFAULT_DISPATCH_GROUP_ACTOR}"
        return {
            "target_session_id": session_id,
            "target_group_id": _group_id_from_session_id(session_id) or "",
        }
    if not isinstance(raw, dict):
        return None
    session_id = str(raw.get("target_session_id") or raw.get("session_id") or "").strip()
    group_id = str(raw.get("target_group_id") or raw.get("group_id") or "").strip()
    if not session_id and group_id:
        session_id = f"group:{group_id}:user:{DEFAULT_DISPATCH_GROUP_ACTOR}"
    if not session_id:
        return None
    return {
        "target_session_id": session_id,
        "target_group_id": group_id or _group_id_from_session_id(session_id) or "",
    }


def _group_id_from_session_id(session_id: str) -> str | None:
    normalized = str(session_id or "").strip()
    if normalized.startswith("group:") and ":user:" in normalized:
        return normalized.split(":", 2)[1]
    return None


def _evaluate_dispatch_policy_gate(
    *,
    ticket_action: str | None,
    target_session_id: str,
    dispatch_runtime_trace: dict[str, Any] | None,
    has_collab_push: bool,
    has_existing_ticket_context: bool,
) -> dict[str, Any]:
    gate_trace = dict((dispatch_runtime_trace or {}).get("policy_gate") or {})
    blocked_execution = bool(gate_trace.get("blocked_execution", False))
    auto_enabled = _truthy_env(os.getenv(DEFAULT_DISPATCH_AUTO_ENV), default=True)
    # Workflow-provided collab_push is an explicit dispatch decision.
    # Keep trace info but avoid dropping delivery due to dispatch agent gate.
    if has_collab_push and target_session_id:
        blocked_execution = False
    normalized_action = str(ticket_action or "").strip()
    is_dispatch_candidate = normalized_action in {
        "create_ticket",
        "handoff",
        "conservative_ticket",
        "clarification_required",
        "new_issue_mode",
    }
    if has_collab_push:
        is_dispatch_candidate = True
    if normalized_action == "new_issue_mode":
        is_dispatch_candidate = True
    elif has_existing_ticket_context and normalized_action in {
        "create_ticket",
        "conservative_ticket",
        "clarification_required",
    }:
        is_dispatch_candidate = True
    if not auto_enabled:
        return {
            "enforced": True,
            "allowed": False,
            "reason": "auto_dispatch_disabled",
            "blocked_execution": blocked_execution,
        }
    if blocked_execution:
        return {
            "enforced": True,
            "allowed": False,
            "reason": "dispatch_agent_policy_blocked",
            "blocked_execution": blocked_execution,
        }
    if not is_dispatch_candidate:
        return {
            "enforced": True,
            "allowed": False,
            "reason": "ticket_action_not_dispatchable",
            "blocked_execution": blocked_execution,
        }
    if not target_session_id:
        return {
            "enforced": True,
            "allowed": False,
            "reason": "no_target_mapping",
            "blocked_execution": blocked_execution,
        }
    return {
        "enforced": True,
        "allowed": True,
        "reason": "allowed",
        "blocked_execution": blocked_execution,
    }


def _resolve_collab_message(
    *,
    ticket_id: str | None,
    queue: str,
    priority: str,
    ticket_action: str | None,
    dispatch_decision: dict[str, Any],
    collab_push: dict[str, Any] | None,
    source_message_text: str,
    has_existing_ticket_context: bool,
) -> str:
    summary = str(dispatch_decision.get("answer") or "").strip()
    ticket_label = ticket_id or "UNKNOWN"
    queue_label = queue or "support"
    priority_label = _format_priority_label(priority)
    summary_message = (
        f"新工单 {ticket_label} 已创建，建议队列：{queue_label}，优先级：{priority_label}。"
        f" 调度说明：{summary or '请优先接单并按SLA推进。'}"
    )
    if collab_push is not None:
        text = str(collab_push.get("message") or "").strip()
        source = str(collab_push.get("source") or "").strip()
        command = str(collab_push.get("command") or "").strip()
        if text and (source == "collab_command" or command):
            return text
    detail_text = ""
    if collab_push is not None:
        detail_text = _sanitize_collab_detail_text(
            str(collab_push.get("message") or "").strip(),
            fallback_text=source_message_text,
        )
    if not detail_text:
        detail_text = str(source_message_text or "").strip()
    compact_detail = re.sub(r"\s+", " ", detail_text).strip()
    if len(compact_detail) > 800:
        compact_detail = f"{compact_detail[:800].rstrip()}…"
    reported_by = str((collab_push or {}).get("customer_id") or "").strip() or "未知"
    reported_at = str((collab_push or {}).get("created_at") or "").strip()
    if reported_at:
        reported_at = reported_at.replace("T", " ").split("+", 1)[0]
    else:
        reported_at = time.strftime("%Y-%m-%d %H:%M")
    normalized_action = str(ticket_action or "").strip()
    if normalized_action in {"create_ticket", "handoff", "conservative_ticket"} and not has_existing_ticket_context:
        detail_line = compact_detail or "（未提供问题描述）"
        return (
            f"新工单 {ticket_label} 已创建\n"
            "────────────────\n"
            f"📌 优先级：{priority_label}\n"
            f"📥 队列：人工接力 / {queue_label}\n"
            f"👤 报修人：{reported_by}\n"
            f"🕒 报修时间：{reported_at}\n"
            "────────────────\n"
            f"📝 工单详情：{detail_line}"
        )
    if normalized_action == "clarification_required":
        if compact_detail:
            return (
                f"工单 {ticket_label} 当前信息待补充，系统已引导报修人继续补充。"
                f"\n补充线索：{compact_detail}"
            )
        return f"工单 {ticket_label} 当前信息待补充，系统已引导报修人继续补充。"
    if has_existing_ticket_context:
        if compact_detail:
            return f"工单 {ticket_label} 收到补充信息：{compact_detail}"
        return f"工单 {ticket_label} 收到新的补充信息，请处理人员关注。"
    if compact_detail:
        return f"{summary_message}\n工单详情：{compact_detail}"
    return summary_message


def _sanitize_collab_detail_text(raw_text: str, *, fallback_text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(raw_text or "")).strip()
    if not normalized:
        return re.sub(r"\s+", " ", str(fallback_text or "")).strip()
    lowered = normalized.lower()
    if not any(marker in lowered for marker in _MACHINE_DETAIL_MARKERS):
        return normalized
    extracted = _extract_machine_detail_segment(normalized)
    if extracted:
        return extracted
    return re.sub(r"\s+", " ", str(fallback_text or "")).strip()


def _extract_machine_detail_segment(machine_text: str) -> str:
    latest_match = re.search(r"(?:^|\|)\s*latest=([^|]+)", machine_text, flags=re.IGNORECASE)
    if latest_match is not None:
        candidate = latest_match.group(1)
        cleaned = _clean_detail_segment(candidate)
        if cleaned:
            return cleaned
    summary_match = re.search(r"(?:^|\|)\s*summary=([^|]+)", machine_text, flags=re.IGNORECASE)
    if summary_match is not None:
        candidate = summary_match.group(1)
        cleaned = _clean_detail_segment(candidate)
        if cleaned:
            return cleaned
    return ""


def _clean_detail_segment(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = cleaned.strip("\"'[](){} ")
    if cleaned.lower().startswith("latest="):
        cleaned = cleaned[7:].strip()
    return cleaned


def _build_group_fast_reply(
    *,
    chat_type: str,
    ticket_action: str | None,
    ticket_id: str | None,
    priority: str,
    reply_text: str,
) -> str | None:
    if str(chat_type or "").strip().lower() != "group":
        return None
    detail = str(reply_text or "").strip()
    action = str(ticket_action or "").strip()
    if action.startswith("collab_"):
        return None
    ticket_label = ticket_id or "UNKNOWN"
    if action in {"create_ticket", "handoff", "conservative_ticket"}:
        return (
            f"已受理，工单 {ticket_label} 已创建，优先级：{_format_priority_label(priority)}。"
            "\n详细处理说明已私发给你，请留意。"
        )
    if action == "progress_reply":
        return f"已收到进度查询，工单 {ticket_label} 的详细进展已私发给你，请留意。"
    if action == "clarification_required":
        return detail
    if len(detail) < DEFAULT_GROUP_FAST_REPLY_MIN_CHARS:
        return None
    return f"已收到，工单 {ticket_label} 的详细处理说明已私发给你，请留意。"


def _should_send_private_detail(*, ticket_action: str | None, reply_text: str) -> bool:
    action = str(ticket_action or "").strip()
    if action in {"new_issue_mode", "session_end", "clarification_required"}:
        return False
    normalized = re.sub(r"\s+", " ", str(reply_text or "")).strip()
    if not normalized:
        return False
    if any(phrase in normalized for phrase in _PRIVATE_DETAIL_SUPPRESS_PHRASES):
        return False
    return True


def _format_priority_label(priority: str) -> str:
    normalized = str(priority or "").strip().upper() or "P3"
    zh_label = _PRIORITY_LABELS_ZH.get(normalized, "普通")
    return f"{zh_label}（{normalized}）"


def _safe_group_id(*, chat_id: str, session_id: str) -> str:
    chat = str(chat_id or "").strip()
    if chat and chat.startswith("wr"):
        return chat
    normalized = str(session_id or "").strip()
    if normalized.startswith("group:") and ":user:" in normalized:
        return normalized.split(":", 2)[1].strip()
    return chat


def _send_private_detail(
    *,
    runtime: _RuntimeLike,
    channel: str,
    session_id: str,
    body: str,
    metadata: dict[str, Any],
) -> None:
    retry_attempts = _private_detail_retry_attempts()
    retry_delay_seconds = _private_detail_retry_delay_seconds()
    if not _truthy_env(os.getenv(DEFAULT_PRIVATE_DETAIL_ASYNC_ENV), default=True):
        _send_private_detail_with_retry(
            runtime,
            channel=channel,
            session_id=session_id,
            body=body,
            metadata=metadata,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
        return

    _trace_dispatch_event(
        runtime,
        event_type="wecom_private_detail_async_scheduled",
        trace_id=str(metadata.get("trace_id") or ""),
        ticket_id=str(metadata.get("ticket_id") or "").strip() or None,
        session_id=session_id,
        payload={
            "channel": channel,
            "session_id": session_id,
            "outbound_type": str(metadata.get("outbound_type") or ""),
            "system": str(metadata.get("system") or ""),
            "dispatch_matched_key": metadata.get("dispatch_matched_key"),
            "body_chars": len(str(body or "")),
            "retry_attempts": retry_attempts,
            "retry_delay_ms": int(retry_delay_seconds * 1000),
        },
    )

    thread = threading.Thread(
        target=_send_private_detail_with_retry,
        kwargs={
            "runtime": runtime,
            "channel": channel,
            "session_id": session_id,
            "body": body,
            "metadata": metadata,
            "retry_attempts": retry_attempts,
            "retry_delay_seconds": retry_delay_seconds,
        },
        daemon=True,
        name="wecom-private-detail",
    )
    thread.start()


def _bind_private_detail_ticket_context(
    *,
    runtime: _RuntimeLike,
    session_id: str,
    ticket_id: str | None,
    source_session_id: str,
    trace_id: str,
) -> None:
    normalized_ticket_id = str(ticket_id or "").strip()
    if not normalized_ticket_id:
        return
    ticket_api = _resolve_ticket_api(runtime)
    bind_session_ticket = getattr(ticket_api, "bind_session_ticket", None)
    if not callable(bind_session_ticket):
        return
    metadata = {
        "source": "wecom_group_private_detail",
        "source_session_id": source_session_id,
        "trace_id": trace_id,
    }
    try:
        bind_session_ticket(session_id, normalized_ticket_id, metadata=metadata)
    except Exception as exc:
        _trace_dispatch_event(
            runtime,
            event_type="wecom_private_detail_session_bind_failed",
            trace_id=trace_id,
            ticket_id=normalized_ticket_id,
            session_id=session_id,
            payload={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "source_session_id": source_session_id,
            },
        )
        return
    _trace_dispatch_event(
        runtime,
        event_type="wecom_private_detail_session_bound",
        trace_id=trace_id,
        ticket_id=normalized_ticket_id,
        session_id=session_id,
        payload={"source_session_id": source_session_id},
    )


def _resolve_ticket_api(runtime: _RuntimeLike) -> Any | None:
    direct = getattr(runtime, "ticket_api", None)
    if direct is not None:
        return direct
    intake = getattr(runtime, "intake_workflow", None)
    if intake is None:
        return None
    from_intake = getattr(intake, "_ticket_api", None)
    if from_intake is not None:
        return from_intake
    return getattr(intake, "ticket_api", None)


def _send_private_detail_with_retry(
    runtime: _RuntimeLike,
    *,
    channel: str,
    session_id: str,
    body: str,
    metadata: dict[str, Any],
    retry_attempts: int,
    retry_delay_seconds: float,
) -> None:
    max_attempts = max(1, int(retry_attempts))
    trace_id = str(metadata.get("trace_id") or "")
    ticket_id = str(metadata.get("ticket_id") or "").strip() or None
    for attempt in range(1, max_attempts + 1):
        sent = _send_outbound_if_supported(
            runtime,
            channel=channel,
            session_id=session_id,
            body=body,
            metadata=metadata,
        )
        _trace_dispatch_event(
            runtime,
            event_type="wecom_private_detail_attempt",
            trace_id=trace_id,
            ticket_id=ticket_id,
            session_id=session_id,
            payload={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "sent": sent,
                "retry_delay_ms": int(retry_delay_seconds * 1000),
            },
        )
        if sent:
            _trace_dispatch_event(
                runtime,
                event_type="wecom_private_detail_delivered",
                trace_id=trace_id,
                ticket_id=ticket_id,
                session_id=session_id,
                payload={"attempt": attempt, "max_attempts": max_attempts},
            )
            return
        if attempt < max_attempts and retry_delay_seconds > 0:
            time.sleep(retry_delay_seconds)
    _trace_dispatch_event(
        runtime,
        event_type="wecom_private_detail_failed",
        trace_id=trace_id,
        ticket_id=ticket_id,
        session_id=session_id,
        payload={"attempts": max_attempts},
    )


def _send_outbound_if_supported(
    runtime: _RuntimeLike,
    *,
    channel: str,
    session_id: str,
    body: str,
    metadata: dict[str, Any],
) -> bool:
    sender = getattr(runtime.gateway, "send_outbound", None)
    if not callable(sender):
        return False
    dedup_decision = _dedupe_group_template_message(
        session_id=session_id,
        metadata=metadata,
    )
    if dedup_decision["suppress"]:
        _trace_dispatch_event(
            runtime,
            event_type="wecom_group_template_dedup_suppressed",
            trace_id=str(metadata.get("trace_id") or ""),
            ticket_id=str(metadata.get("ticket_id") or "").strip() or None,
            session_id=session_id,
            payload={
                "target_group_id": dedup_decision["group_id"],
                "template_key": dedup_decision["template_key"],
                "dedup_window_seconds": dedup_decision["window_seconds"],
                "reason": "same_group_ticket_template_within_window",
            },
        )
        return True
    chunks = _split_outbound_body(channel=channel, body=body)
    total_chunks = len(chunks)
    try:
        for index, chunk in enumerate(chunks, start=1):
            chunk_metadata = dict(metadata)
            if total_chunks > 1:
                chunk_metadata["chunked"] = True
                chunk_metadata["chunk_index"] = index
                chunk_metadata["chunk_total"] = total_chunks
            sender(
                channel=channel,
                session_id=session_id,
                body=chunk,
                metadata=chunk_metadata,
            )
    except Exception:
        return False
    return True


def _dedupe_group_template_message(
    *,
    session_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    outbound_type = str(metadata.get("outbound_type") or "").strip()
    template_key = str(metadata.get("reply_mode") or "").strip()
    ticket_id = str(metadata.get("ticket_id") or "").strip()
    group_id = (
        str(metadata.get("target_group_id") or "").strip()
        or _group_id_from_session_id(session_id)
        or ""
    )
    window_seconds = _group_template_dedup_window_seconds()
    if outbound_type != "user_receipt":
        return {
            "suppress": False,
            "group_id": group_id,
            "template_key": template_key,
            "window_seconds": window_seconds,
        }
    if template_key != "group_fast_rule" or not ticket_id or not group_id or window_seconds <= 0:
        return {
            "suppress": False,
            "group_id": group_id,
            "template_key": template_key,
            "window_seconds": window_seconds,
        }

    now = time.monotonic()
    cache_key = (group_id, ticket_id, template_key)
    suppress = False
    with _GROUP_TEMPLATE_DEDUP_LOCK:
        previous = _GROUP_TEMPLATE_DEDUP_CACHE.get(cache_key)
        if previous is not None and now - previous < window_seconds:
            suppress = True
        else:
            _GROUP_TEMPLATE_DEDUP_CACHE[cache_key] = now
        stale_threshold = now - window_seconds
        stale_keys = [
            key for key, ts in _GROUP_TEMPLATE_DEDUP_CACHE.items() if ts < stale_threshold
        ]
        for key in stale_keys:
            _GROUP_TEMPLATE_DEDUP_CACHE.pop(key, None)
    return {
        "suppress": suppress,
        "group_id": group_id,
        "template_key": template_key,
        "window_seconds": window_seconds,
    }


def _split_outbound_body(*, channel: str, body: str) -> list[str]:
    text = str(body or "").strip()
    if not text:
        return [""]
    if channel.strip().lower() != "wecom":
        return [text]

    chunk_size = _wecom_outbound_chunk_chars()
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    remaining = text
    min_boundary = max(60, int(chunk_size * 0.35))
    while len(remaining) > chunk_size:
        window = remaining[:chunk_size]
        split_at = _best_split_boundary(window)
        if split_at < min_boundary:
            split_at = chunk_size
        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:chunk_size]
            split_at = len(chunk)
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks or [text]


def _group_template_dedup_window_seconds() -> int:
    raw = os.getenv(DEFAULT_GROUP_TEMPLATE_DEDUP_WINDOW_SECONDS_ENV, "").strip()
    if not raw:
        return DEFAULT_GROUP_TEMPLATE_DEDUP_WINDOW_SECONDS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_GROUP_TEMPLATE_DEDUP_WINDOW_SECONDS
    return max(0, min(parsed, 3600))


def _best_split_boundary(window: str) -> int:
    priority_groups: tuple[tuple[str, ...], ...] = (
        ("\n\n", "\n"),
        ("。", "！", "？", "；", ";", ".", ":", "："),
        ("，", ",", "、", " "),
    )
    for group in priority_groups:
        best_end = -1
        for marker in group:
            marker_pos = window.rfind(marker)
            if marker_pos >= 0:
                best_end = max(best_end, marker_pos + len(marker))
        if best_end >= 0:
            return best_end
    return -1


def _wecom_outbound_chunk_chars() -> int:
    raw = os.getenv(DEFAULT_WECOM_OUTBOUND_CHUNK_CHARS_ENV, "").strip()
    if not raw:
        return DEFAULT_WECOM_OUTBOUND_CHUNK_CHARS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_WECOM_OUTBOUND_CHUNK_CHARS
    return max(200, min(parsed, 3000))


def _trace_dispatch_event(
    runtime: _RuntimeLike,
    *,
    event_type: str,
    trace_id: str,
    ticket_id: str | None,
    session_id: str,
    payload: dict[str, Any],
) -> None:
    bindings = getattr(runtime.gateway, "bindings", None)
    trace_logger = getattr(bindings, "trace_logger", None) if bindings is not None else None
    if trace_logger is None or not hasattr(trace_logger, "log"):
        return
    trace_logger.log(
        event_type,
        payload,
        trace_id=trace_id,
        ticket_id=ticket_id,
        session_id=session_id,
    )


def _truthy_env(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _private_detail_retry_attempts() -> int:
    raw = os.getenv(DEFAULT_PRIVATE_DETAIL_RETRY_ATTEMPTS_ENV, "").strip()
    if not raw:
        return DEFAULT_PRIVATE_DETAIL_RETRY_ATTEMPTS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_PRIVATE_DETAIL_RETRY_ATTEMPTS
    return max(1, min(parsed, 8))


def _private_detail_retry_delay_seconds() -> float:
    raw = os.getenv(DEFAULT_PRIVATE_DETAIL_RETRY_DELAY_MS_ENV, "").strip()
    if not raw:
        return DEFAULT_PRIVATE_DETAIL_RETRY_DELAY_MS / 1000
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_PRIVATE_DETAIL_RETRY_DELAY_MS / 1000
    parsed = max(0, min(parsed, 5000))
    return parsed / 1000


def _compose_session_id(*, sender_id: str, chat_id: str, chat_type: str) -> str:
    if chat_type == "group":
        return f"group:{chat_id}:user:{sender_id}"
    return f"dm:{sender_id}"


def _pick_string(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _pick_nested(payload, key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _pick_text(payload: dict[str, Any]) -> str:
    for key in (
        "text",
        "Content",
        "content",
        "text.content",
        "message.text",
        "message.content",
        "msg.text",
        "msg.content",
    ):
        value = _pick_nested(payload, key)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
        if isinstance(value, dict):
            nested = value.get("content")
            if nested is not None:
                text = str(nested).strip()
                if text:
                    return text
    return ""


def _pick_nested(payload: dict[str, Any], key: str) -> Any:
    if "." not in key:
        return payload.get(key)
    current: Any = payload
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _build_fallback_msg_id(*, payload: dict[str, Any], req_id: str) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    req_part = req_id.strip() or "trace"
    return f"bridge:{req_part}:{digest}"


def _build_handler(*, runtime: _RuntimeLike, path: str) -> type[BaseHTTPRequestHandler]:
    route_path = path

    class BridgeHandler(BaseHTTPRequestHandler):
        server_version = "SupportAgentWeComBridge/1.0"

        def do_POST(self) -> None:
            if urlparse(self.path).path != route_path:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            try:
                body = self._read_json_body()
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            try:
                result = process_wecom_message(runtime, body)
            except Exception:
                result = BridgeResult(
                    handled=True,
                    reply_text=DEFAULT_REPLY_ON_ERROR,
                    status="runtime_error",
                )
            self._write_json(HTTPStatus.OK, result.as_json())

        def do_GET(self) -> None:
            if urlparse(self.path).path != "/healthz":
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._write_json(HTTPStatus.OK, {"status": "ok"})

        def _read_json_body(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("missing content-length")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ValueError("invalid content-length") from exc
            if length <= 0:
                raise ValueError("empty body")
            data = self.rfile.read(length)
            try:
                decoded = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("invalid json") from exc
            if not isinstance(decoded, dict):
                raise ValueError("json body must be object")
            return decoded

        def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    return BridgeHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WeCom -> workflow bridge server")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument(
        "--host",
        default=os.getenv("WECOM_BRIDGE_HOST", "127.0.0.1"),
        help="HTTP bind host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WECOM_BRIDGE_PORT", "18081")),
        help="HTTP bind port",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("WECOM_BRIDGE_PATH", DEFAULT_BRIDGE_PATH),
        help="Bridge POST path",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable dev auto-reload when source files change",
    )
    parser.add_argument(
        "--reload-interval",
        type=float,
        default=float(os.getenv("SUPPORT_AGENT_RELOAD_INTERVAL", "1.0")),
        help="Polling interval seconds for --reload",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.reload and os.getenv(RELOADER_CHILD_ENV) != "1":
        repo_root = Path(__file__).resolve().parents[1]
        return run_with_reloader(
            argv=[sys.executable, "-m", "scripts.wecom_bridge_server", *sys.argv[1:]],
            watch_roots=build_default_watch_roots(repo_root),
            interval_seconds=args.reload_interval,
            service_name="wecom_bridge_server",
        )
    runtime = build_runtime(args.env)
    handler = _build_handler(runtime=runtime, path=args.path)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "status": "starting",
                "host": args.host,
                "port": args.port,
                "path": args.path,
                "healthz": "/healthz",
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
