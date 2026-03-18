from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from channel_adapters.base import ChannelAdapterError
from core.trace_logger import new_trace_id

_REPLY_EVENT_TYPES = {
    "reply_draft_generated",
    "reply_send_requested",
    "reply_send_delivered",
    "reply_send_failed",
    "reply_send_retry_scheduled",
    "reply_send_dedup_hit",
}


def run_reply_draft_v2(
    runtime: Any,
    *,
    ticket_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    actor_id = str(payload.get("actor_id") or "ops-api").strip() or "ops-api"
    actor_role = _resolve_actor_role(payload.get("actor_role"), actor_id=actor_id)
    style = str(payload.get("style") or "说明").strip() or "说明"
    max_length = _coerce_max_length(payload.get("max_length"))
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()

    style_profile = _resolve_draft_style_profile(style)
    draft_text = _build_draft_text(
        ticket=ticket,
        style=style,
        style_profile=style_profile,
    )
    draft_text = _truncate(draft_text, max_length=max_length)
    risk_flags = _draft_risk_flags(draft_text)
    grounding = {
        "ticket_id": ticket.ticket_id,
        "session_id": ticket.session_id,
        "queue": ticket.queue,
        "status": ticket.status,
    }

    event_payload = {
        "ticket_id": ticket.ticket_id,
        "session_id": ticket.session_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "style": style,
        "style_effective": style_profile["key"],
        "max_length": max_length,
        "advice_only": True,
        "risk_flags": risk_flags,
        "grounding": grounding,
        "draft_text": draft_text,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    runtime.ticket_api.add_event(
        ticket.ticket_id,
        event_type="reply_draft_generated",
        actor_type="agent",
        actor_id=actor_id,
        payload=event_payload,
    )
    runtime.trace_logger.log(
        "reply_draft_generated",
        event_payload,
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    return {
        "ticket_id": ticket.ticket_id,
        "session_id": ticket.session_id,
        "draft_text": draft_text,
        "risk_flags": risk_flags,
        "grounding": grounding,
        "advice_only": True,
        "trace_id": trace_id,
        "style_effective": style_profile["key"],
    }


def run_reply_send_v2(
    runtime: Any,
    *,
    ticket_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    actor_id = str(payload.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")
    actor_role = _resolve_actor_role(payload.get("actor_role"), actor_id=actor_id)
    if actor_role == "observer":
        raise PermissionError("observer role cannot send replies")

    content = str(payload.get("content") or "").strip()
    if not content:
        raise ValueError("content is required")
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if not idempotency_key:
        raise ValueError("idempotency_key is required")
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()
    session_id = str(payload.get("session_id") or ticket.session_id).strip() or ticket.session_id
    draft_source = str(payload.get("draft_source") or "manual").strip() or "manual"

    target_user_id = _resolve_target_user_id(ticket=ticket, payload=payload, session_id=session_id)
    target_session_id = f"dm:{target_user_id}"
    reply_id = _build_reply_id(ticket_id=ticket.ticket_id, idempotency_key=idempotency_key)

    delivered_event = runtime.repository.find_event_by_idempotency_key(
        ticket_id=ticket.ticket_id,
        event_type="reply_send_delivered",
        idempotency_key=idempotency_key,
    )
    if delivered_event is not None:
        dedup_payload = dict(delivered_event.payload or {})
        dedup_status = str(dedup_payload.get("delivery_status") or "sent").strip() or "sent"
        dedup_event_payload = {
            "reply_id": str(dedup_payload.get("reply_id") or reply_id),
            "ticket_id": ticket.ticket_id,
            "session_id": session_id,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "idempotency_key": idempotency_key,
            "delivery_status": dedup_status,
            "dedup_hit": True,
            "attempt": int(dedup_payload.get("attempt") or 1),
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        runtime.ticket_api.add_event(
            ticket.ticket_id,
            event_type="reply_send_dedup_hit",
            actor_type="agent",
            actor_id=actor_id,
            payload=dedup_event_payload,
        )
        runtime.trace_logger.log(
            "reply_send_dedup_hit",
            dedup_event_payload,
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=session_id,
        )
        return {
            "reply_id": dedup_event_payload["reply_id"],
            "delivery_status": dedup_status,
            "channel": "wecom",
            "target": {"to_user_id": target_user_id, "session_id": target_session_id},
            "trace_id": trace_id,
            "dedup_hit": True,
            "attempt": dedup_event_payload["attempt"],
            "error": None,
        }

    attempt = _next_attempt(runtime=runtime, ticket_id=ticket.ticket_id, idempotency_key=idempotency_key)
    requested_payload = {
        "reply_id": reply_id,
        "ticket_id": ticket.ticket_id,
        "session_id": session_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "draft_source": draft_source,
        "idempotency_key": idempotency_key,
        "trace_id": trace_id,
        "to_user_id": target_user_id,
        "target_session_id": target_session_id,
        "attempt": attempt,
        "content_preview": _truncate(content, max_length=160),
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    runtime.ticket_api.add_event(
        ticket.ticket_id,
        event_type="reply_send_requested",
        actor_type="agent",
        actor_id=actor_id,
        payload=requested_payload,
    )
    runtime.trace_logger.log(
        "reply_send_requested",
        requested_payload,
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=session_id,
    )

    delivery_status = "queued"
    delivery_payload: dict[str, Any] = {}
    failure_message: str | None = None
    try:
        delivery_payload = runtime.gateway.send_outbound(
            channel="wecom",
            session_id=target_session_id,
            body=content,
            metadata={
                "trace_id": trace_id,
                "ticket_id": ticket.ticket_id,
                "session_id": session_id,
                "outbound_type": "manual_reply",
                "target_user_id": target_user_id,
                "reply_id": reply_id,
                "idempotency_key": idempotency_key,
                "actor_id": actor_id,
                "draft_source": draft_source,
            },
        )
        mode = str(delivery_payload.get("mode") or "").strip().lower()
        delivery_status = "sent" if mode == "api_sent" else "queued"
        delivered_payload = {
            **requested_payload,
            "delivery_status": delivery_status,
            "delivery": delivery_payload,
            "error": None,
        }
        runtime.ticket_api.add_event(
            ticket.ticket_id,
            event_type="reply_send_delivered",
            actor_type="agent",
            actor_id=actor_id,
            payload=delivered_payload,
        )
        runtime.trace_logger.log(
            "reply_send_delivered",
            delivered_payload,
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=session_id,
        )
    except ChannelAdapterError as exc:
        failure_message = str(exc)
        _record_reply_send_failed(
            runtime=runtime,
            ticket=ticket,
            session_id=session_id,
            trace_id=trace_id,
            actor_id=actor_id,
            actor_role=actor_role,
            draft_source=draft_source,
            idempotency_key=idempotency_key,
            reply_id=reply_id,
            attempt=attempt,
            target_user_id=target_user_id,
            error_message=failure_message,
            retryable=bool(exc.retryable),
        )
        delivery_status = "failed"
    except Exception as exc:  # pragma: no cover - defensive fallback
        failure_message = str(exc)
        _record_reply_send_failed(
            runtime=runtime,
            ticket=ticket,
            session_id=session_id,
            trace_id=trace_id,
            actor_id=actor_id,
            actor_role=actor_role,
            draft_source=draft_source,
            idempotency_key=idempotency_key,
            reply_id=reply_id,
            attempt=attempt,
            target_user_id=target_user_id,
            error_message=failure_message,
            retryable=False,
        )
        delivery_status = "failed"

    return {
        "reply_id": reply_id,
        "delivery_status": delivery_status,
        "channel": "wecom",
        "target": {"to_user_id": target_user_id, "session_id": target_session_id},
        "trace_id": trace_id,
        "dedup_hit": False,
        "attempt": attempt,
        "error": failure_message,
        "delivery": delivery_payload,
    }


def is_reply_event_type(event_type: str) -> bool:
    normalized = str(event_type or "").strip()
    return normalized in _REPLY_EVENT_TYPES or normalized == "reply_generated"


def _resolve_actor_role(raw_role: Any, *, actor_id: str) -> str:
    normalized = str(raw_role or "").strip().lower().replace("-", "_")
    if normalized in {"observer", "viewer", "read_only", "readonly"}:
        return "observer"
    if normalized in {"operator", "agent", "supervisor", "admin"}:
        return normalized
    actor = actor_id.strip().lower()
    if "observer" in actor or actor.startswith("u_viewer"):
        return "observer"
    if "supervisor" in actor or actor.startswith("u_supervisor"):
        return "supervisor"
    return "operator"


def _build_draft_text(*, ticket: Any, style: str, style_profile: dict[str, str]) -> str:
    summary = str(ticket.title or ticket.latest_message or "").strip()
    detail = str(ticket.latest_message or "").strip()
    detail_snippet = detail[:120] if detail else ""
    status_text = _resolve_status_phrase(ticket)
    opening = style_profile["opening"]
    action = style_profile["action"]
    closing = style_profile["closing"]
    tone_tag = style_profile["tone_tag"]
    return (
        f"{opening}关于工单 {ticket.ticket_id}（{summary}），当前进度：{status_text}。"
        f"{action}"
        f"{detail_snippet}"
        f"{closing}（风格：{style}/{tone_tag}）"
    ).strip()


def _resolve_status_phrase(ticket: Any) -> str:
    status = str(getattr(ticket, "status", "") or "").strip() or "unknown"
    handoff_state = str(getattr(ticket, "handoff_state", "") or "").strip() or "none"
    if status == "handoff":
        return f"已进入人工接管（handoff_state={handoff_state}）"
    if status in {"resolved", "closed", "completed"}:
        return "问题已完成处理，待结果确认"
    if handoff_state in {"pending_claim", "claimed", "waiting_internal", "waiting_customer"}:
        return f"人工流转中（handoff_state={handoff_state}）"
    return f"处理中（status={status}）"


def _resolve_draft_style_profile(style: str) -> dict[str, str]:
    normalized = style.strip().lower()
    if any(keyword in normalized for keyword in ("安抚", "抱歉", "温和", "同理", "耐心")):
        return {
            "key": "empathy",
            "tone_tag": "安抚同理",
            "opening": "您好，给您带来不便我们非常抱歉。",
            "action": "我们已第一时间安排同事跟进并持续回传进展；",
            "closing": "若您方便，也请补充现场时间点或截图，我们会优先处理。",
        }
    if any(keyword in normalized for keyword in ("已处理", "完成", "结论", "闭环", "结果")):
        return {
            "key": "resolved",
            "tone_tag": "结果导向",
            "opening": "您好，处理结果已更新。",
            "action": "当前已完成主要处置动作；",
            "closing": "请您核验体验是否恢复，若仍异常我们将立即继续处理。",
        }
    if any(keyword in normalized for keyword in ("紧急", "催办", "升级", "加急", "优先")):
        return {
            "key": "urgent",
            "tone_tag": "紧急推进",
            "opening": "您好，该问题已按紧急级别处理。",
            "action": "我们已加急联动值班同事并优先排查；",
            "closing": "请保持联系方式畅通，我们会在下一次进展出现后立即回告。",
        }
    if any(keyword in normalized for keyword in ("简短", "简洁", "一句话", "短")):
        return {
            "key": "concise",
            "tone_tag": "简洁直给",
            "opening": "您好，已收到并在处理。",
            "action": "",
            "closing": "有新进展会第一时间通知您。",
        }
    return {
        "key": "explain",
        "tone_tag": "说明",
        "opening": "您好，您的问题我们已收到。",
        "action": "目前正在按流程排查并推进处理；",
        "closing": "如有补充信息请直接回复，我们会据此加快处理。",
    }


def _resolve_target_user_id(*, ticket: Any, payload: dict[str, Any], session_id: str) -> str:
    explicit = str(payload.get("to_user_id") or "").strip()
    if explicit:
        return explicit
    explicit_session = str(payload.get("target_session_id") or "").strip()
    if explicit_session.startswith("dm:"):
        suffix = explicit_session[3:].strip()
        if suffix:
            return suffix
    if getattr(ticket, "customer_id", None):
        value = str(ticket.customer_id).strip()
        if value:
            return value
    metadata = dict(getattr(ticket, "metadata", {}) or {})
    for key in ("to_user_id", "sender_id", "from_userid", "from_user_id", "user_id", "userid"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    if session_id.startswith("dm:"):
        suffix = session_id[3:].strip()
        if suffix:
            return suffix
    if session_id.startswith("group:") and ":user:" in session_id:
        suffix = session_id.rsplit(":user:", 1)[-1].strip()
        if suffix:
            return suffix
    raise ValueError("to_user_id cannot be resolved from payload/ticket/session")


def _build_reply_id(*, ticket_id: str, idempotency_key: str) -> str:
    digest = hashlib.sha1(idempotency_key.encode("utf-8")).hexdigest()[:12]
    return f"reply_{ticket_id}_{digest}"


def _next_attempt(*, runtime: Any, ticket_id: str, idempotency_key: str) -> int:
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        return 1
    max_attempt = 0
    for event in runtime.ticket_api.list_events(ticket_id):
        if str(event.event_type or "").strip() not in {
            "reply_send_requested",
            "reply_send_delivered",
            "reply_send_failed",
            "reply_send_retry_scheduled",
        }:
            continue
        payload = dict(event.payload or {}) if isinstance(event.payload, dict) else {}
        if str(payload.get("idempotency_key") or "").strip() != normalized_key:
            continue
        try:
            attempt = int(payload.get("attempt") or 0)
        except (TypeError, ValueError):
            attempt = 0
        max_attempt = max(max_attempt, attempt)
    return max_attempt + 1 if max_attempt > 0 else 1


def _record_reply_send_failed(
    *,
    runtime: Any,
    ticket: Any,
    session_id: str,
    trace_id: str,
    actor_id: str,
    actor_role: str,
    draft_source: str,
    idempotency_key: str,
    reply_id: str,
    attempt: int,
    target_user_id: str,
    error_message: str,
    retryable: bool,
) -> None:
    failed_payload = {
        "reply_id": reply_id,
        "ticket_id": ticket.ticket_id,
        "session_id": session_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "draft_source": draft_source,
        "idempotency_key": idempotency_key,
        "trace_id": trace_id,
        "to_user_id": target_user_id,
        "attempt": attempt,
        "delivery_status": "failed",
        "error": error_message,
        "retryable": retryable,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    runtime.ticket_api.add_event(
        ticket.ticket_id,
        event_type="reply_send_failed",
        actor_type="agent",
        actor_id=actor_id,
        payload=failed_payload,
    )
    runtime.trace_logger.log(
        "reply_send_failed",
        failed_payload,
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=session_id,
    )
    retry_payload = {
        **failed_payload,
        "next_attempt": attempt + 1,
    }
    runtime.ticket_api.add_event(
        ticket.ticket_id,
        event_type="reply_send_retry_scheduled",
        actor_type="agent",
        actor_id=actor_id,
        payload=retry_payload,
    )
    runtime.trace_logger.log(
        "reply_send_retry_scheduled",
        retry_payload,
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=session_id,
    )


def _coerce_max_length(raw: Any) -> int:
    try:
        value = int(raw) if raw is not None else 240
    except (TypeError, ValueError):
        value = 240
    return max(60, min(value, 1000))


def _truncate(text: str, *, max_length: int) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"


def _draft_risk_flags(text: str) -> list[str]:
    lowered = str(text or "").lower()
    flags: list[str] = []
    for keyword, flag in (
        ("赔偿", "compensation_sensitive"),
        ("退款", "refund_sensitive"),
        ("法律", "legal_sensitive"),
        ("投诉", "escalation_sensitive"),
    ):
        if keyword in lowered and flag not in flags:
            flags.append(flag)
    return flags
