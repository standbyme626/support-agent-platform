from __future__ import annotations

from typing import Any, Callable

from core.intent_router import IntentDecision
from core.trace_logger import new_trace_id


def execute_close_compat_action(
    runtime: Any,
    *,
    ticket_id: str,
    actor_id: str,
    payload: dict[str, Any],
    ticket_trace_id_getter: Callable[[Any], str | None],
) -> dict[str, str]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    requested_action = _normalize_close_compat_action(payload.get("action"))
    close_reason = str(payload.get("close_reason") or "").strip().lower()
    inferred_action = _resolve_close_action_by_reason(close_reason)
    if requested_action and inferred_action and requested_action != inferred_action:
        raise ValueError(
            "conflicting close action: action and close_reason resolve to "
            "different terminal semantics"
        )
    resolved_action = requested_action or inferred_action
    session_id = str(payload.get("session_id") or ticket.session_id).strip() or None
    trace_id = str(payload.get("trace_id") or ticket_trace_id_getter(ticket) or new_trace_id()).strip()
    if resolved_action not in {"customer_confirm", "operator_close"}:
        raise ValueError(
            "ambiguous close action; provide "
            "action=customer_confirm|operator_close or deterministic close_reason"
        )

    if resolved_action == "customer_confirm":
        runtime.ticket_api_v2.customer_confirm(
            ticket_id,
            actor_id=actor_id,
            note=str(payload.get("resolution_note") or payload.get("note") or "客户确认关闭"),
            session_id=session_id,
        )
    else:
        runtime.ticket_api_v2.operator_close(
            ticket_id,
            actor_id=actor_id,
            reason=str(payload.get("close_reason") or payload.get("reason") or "operator_forced_close"),
            note=str(payload.get("resolution_note") or payload.get("note") or "处理人关闭"),
            session_id=session_id,
        )

    runtime.ticket_api.add_event(
        ticket_id,
        event_type="ticket_closed",
        actor_type="agent",
        actor_id=actor_id,
        payload={
            "compat_action": resolved_action,
            "requested_action": "close",
            "requested_terminal_action": requested_action,
            "inferred_terminal_action": inferred_action,
            "close_reason": str(payload.get("close_reason") or ""),
            "resolution_note": str(payload.get("resolution_note") or ""),
            "compatibility_mode": "v1_close_forwarded_to_v2",
        },
    )
    runtime.trace_logger.log(
        "ticket_action_v1_close_compat",
        {
            "ticket_id": ticket_id,
            "action": "close",
            "resolved_action": resolved_action,
            "requested_terminal_action": requested_action,
            "inferred_terminal_action": inferred_action,
            "actor_id": actor_id,
            "close_reason": str(payload.get("close_reason") or ""),
            "compatibility_mode": "v1_close_forwarded_to_v2",
        },
        trace_id=trace_id,
        ticket_id=ticket_id,
        session_id=session_id,
    )
    return {
        "event_type": "ticket_closed",
        "resolved_action": resolved_action,
        "trace_id": trace_id,
    }


def build_ticket_assist_payload(
    runtime: Any,
    ticket_id: str,
    *,
    extract_llm_trace_for_ticket: Callable[[Any, Any], dict[str, Any]],
    normalize_llm_trace: Callable[[dict[str, Any]], dict[str, Any]],
    extract_grounding_sources: Callable[[Any, Any], list[dict[str, Any]]],
) -> dict[str, Any]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    events = runtime.ticket_api.list_events(ticket_id)
    summary = runtime.summary_engine.case_summary(ticket, events)
    latest_summary_trace = runtime.summary_engine.last_generation_metadata()
    metadata_cards = ticket.metadata.get("recommended_action_cards")
    recommendations: list[dict[str, Any]]
    if isinstance(metadata_cards, list):
        recommendations = [dict(item) for item in metadata_cards if isinstance(item, dict)]
    else:
        retrieved_docs = runtime.retriever.search_grounded(ticket.latest_message, top_k=3)
        intent = IntentDecision(
            intent=ticket.intent,
            confidence=0.7,
            is_low_confidence=False,
            reason="ticket-intent",
        )
        recommendations = [
            item.as_dict()
            for item in runtime.recommendation_engine.recommend(
                ticket=ticket,
                intent=intent,
                retrieved_docs=retrieved_docs,
                sla_breaches=[],
            )
        ]
    risk_flags = sorted(
        {
            str(item.get("risk", ""))
            for item in recommendations
            if isinstance(item, dict) and item.get("risk")
        }
    )
    llm_trace = extract_llm_trace_for_ticket(runtime, ticket)
    if latest_summary_trace:
        llm_trace = {**llm_trace, **normalize_llm_trace(latest_summary_trace)}
    if llm_trace.get("degraded"):
        risk_flags = sorted({*risk_flags, "llm_degraded"})
    ticket_grounding_sources = extract_grounding_sources(ticket, runtime.retriever)
    return {
        "summary": summary,
        "recommended_actions": recommendations,
        "grounding_sources": ticket_grounding_sources,
        "risk_flags": risk_flags,
        "latest_messages": [ticket.latest_message],
        "provider": llm_trace.get("provider") or runtime.app_config.llm.provider,
        "model": llm_trace.get("model"),
        "prompt_key": llm_trace.get("prompt_key"),
        "prompt_version": llm_trace.get("prompt_version"),
        "latency_ms": llm_trace.get("latency_ms"),
        "request_id": llm_trace.get("request_id"),
        "token_usage": llm_trace.get("token_usage"),
        "retry_count": llm_trace.get("retry_count"),
        "success": llm_trace.get("success"),
        "error": llm_trace.get("error"),
        "fallback_used": llm_trace.get("fallback_used"),
        "degraded": llm_trace.get("degraded"),
        "degrade_reason": llm_trace.get("degrade_reason"),
    }


def _resolve_close_action_by_reason(close_reason: str) -> str | None:
    normalized = close_reason.strip().lower()
    if normalized in {"customer_confirmed", "customer_confirm", "customer-confirm"}:
        return "customer_confirm"
    if normalized in {"operator_forced_close", "agent_close", "manual_close"}:
        return "operator_close"
    return None


def _normalize_close_compat_action(raw_action: Any) -> str | None:
    normalized = str(raw_action or "").strip().replace("-", "_").lower()
    if not normalized:
        return None
    if normalized not in {"customer_confirm", "operator_close"}:
        raise ValueError(
            "unsupported close action; action must be customer_confirm or operator_close"
        )
    return normalized
