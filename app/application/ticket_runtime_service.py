from __future__ import annotations

from typing import Any, Callable

from app.application.collab_service import (
    prepare_collab_action_state,
    resume_collab_action_state_from_payload,
)
from core.hitl.handoff_context import build_approval_context
from core.intent_router import IntentDecision
from core.trace_logger import new_trace_id
from storage.models import Ticket


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


def execute_v2_ticket_action(
    runtime: Any,
    *,
    ticket_id: str,
    action: str,
    actor_id: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    session_id = str(payload.get("session_id") or runtime.ticket_api.require_ticket(ticket_id).session_id).strip()
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()

    if action == "resolve":
        result = runtime.ticket_api_v2.resolve(
            ticket_id,
            actor_id=actor_id,
            resolution_note=str(payload.get("resolution_note") or "已处理"),
            resolution_code=str(payload.get("resolution_code") or "") or None,
            session_id=session_id or None,
        )
    elif action == "customer-confirm":
        result = runtime.ticket_api_v2.customer_confirm(
            ticket_id,
            actor_id=actor_id,
            note=str(payload.get("note") or payload.get("resolution_note") or "customer_confirm"),
            session_id=session_id or None,
        )
    elif action == "operator-close":
        close_reason = str(payload.get("close_reason") or payload.get("reason") or "operator_forced_close")
        result = runtime.ticket_api_v2.operator_close(
            ticket_id,
            actor_id=actor_id,
            reason=close_reason,
            note=str(payload.get("note") or payload.get("resolution_note") or "operator_close"),
            session_id=session_id or None,
        )
    else:
        raise ValueError(f"unsupported v2 action: {action}")

    runtime.trace_logger.log(
        "ticket_action_v2",
        {
            "ticket_id": ticket_id,
            "action": action,
            "event_type": result.event_type,
            "actor_id": actor_id,
        },
        trace_id=trace_id,
        ticket_id=ticket_id,
        session_id=session_id or None,
    )
    return {"event_type": result.event_type, "resolved_action": action, "trace_id": trace_id}


def resolve_action(
    runtime: Any,
    *,
    ticket_id: str,
    action: str,
    body: dict[str, Any],
    ticket_to_dict: Callable[[Any], dict[str, Any]],
    ticket_trace_id_getter: Callable[[Any], str | None],
) -> dict[str, Any]:
    actor_id = str(body.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")

    action_payload = dict(body)
    action_payload["actor_id"] = actor_id
    collab_state = prepare_collab_action_state(
        runtime.collab_service,
        ticket_id=ticket_id,
        action=action,
        actor_id=actor_id,
        payload=action_payload,
    )
    if isinstance(collab_state, dict):
        checkpoint_id = str(collab_state.get("pause_checkpoint_id") or "").strip()
        normalized_action = str(collab_state.get("normalized_action") or "").strip()
        if checkpoint_id:
            action_payload["collab_checkpoint_id"] = checkpoint_id
        if normalized_action:
            action_payload["collab_normalized_action"] = normalized_action
        if collab_state.get("requires_approval") is not None:
            action_payload["collab_requires_approval"] = bool(collab_state["requires_approval"])
    maybe_trace_id = str(body.get("trace_id") or "").strip() or None
    approval_result = runtime.approval_runtime.request_approval_if_needed(
        ticket_id=ticket_id,
        action_type=action,
        actor_id=actor_id,
        payload=action_payload,
        context=build_approval_context(
            ticket=runtime.ticket_api.require_ticket(ticket_id),
            action_type=action,
            payload=action_payload,
        ),
        timeout_minutes=(
            int(body["timeout_minutes"]) if isinstance(body.get("timeout_minutes"), int) else None
        ),
        trace_id=maybe_trace_id,
    )
    if approval_result.requires_approval and approval_result.pending_action is not None:
        ticket_payload = ticket_to_dict(approval_result.ticket)
        ticket_payload.update(
            {
                "approval_required": True,
                "approval_id": approval_result.pending_action.approval_id,
                "approval_status": approval_result.pending_action.status,
                "approval_action_type": approval_result.pending_action.action_type,
                "collab_graph": collab_state,
            }
        )
        return ticket_payload

    if action_payload.get("collab_checkpoint_id"):
        resumed = resume_collab_action_state_from_payload(
            runtime.collab_service,
            pending_payload=action_payload,
            decision="approve",
            actor_id=actor_id,
        )
        if resumed is not None:
            collab_state = resumed

    if action == "claim":
        ticket = runtime.ticket_api.assign_ticket(ticket_id, assignee=actor_id, actor_id=actor_id)
    elif action == "reassign":
        target_queue = str(body.get("target_queue") or "").strip()
        target_assignee = str(body.get("target_assignee") or "").strip()
        updates: dict[str, Any] = {}
        if target_queue:
            updates["queue"] = target_queue
        if updates:
            runtime.ticket_api.update_ticket(ticket_id, updates, actor_id=actor_id)
        ticket = (
            runtime.ticket_api.assign_ticket(ticket_id, assignee=target_assignee, actor_id=actor_id)
            if target_assignee
            else runtime.ticket_api.require_ticket(ticket_id)
        )
        runtime.ticket_api.add_event(
            ticket_id,
            event_type="ticket_reassign_requested",
            actor_type="agent",
            actor_id=actor_id,
            payload={"target_queue": target_queue, "target_assignee": target_assignee},
        )
    elif action == "escalate":
        note = str(body.get("note") or "升级处理")
        ticket = runtime.ticket_api.escalate_ticket(ticket_id, actor_id=actor_id, reason=note)
    elif action == "resolve":
        action_result = execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action="resolve",
            actor_id=actor_id,
            payload=body,
        )
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        result_payload = ticket_to_dict(ticket)
        result_payload["approval_required"] = False
        result_payload["event_type"] = action_result["event_type"]
        result_payload["resolved_action"] = action_result["resolved_action"]
        result_payload["trace_id"] = action_result["trace_id"]
        if collab_state is not None:
            result_payload["collab_graph"] = collab_state
        return result_payload
    elif action in {"customer-confirm", "operator-close"}:
        action_result = execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action=action,
            actor_id=actor_id,
            payload=body,
        )
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        result_payload = ticket_to_dict(ticket)
        result_payload["approval_required"] = False
        result_payload["event_type"] = action_result["event_type"]
        result_payload["resolved_action"] = action_result["resolved_action"]
        result_payload["trace_id"] = action_result["trace_id"]
        if collab_state is not None:
            result_payload["collab_graph"] = collab_state
        return result_payload
    elif action == "close":
        action_result = execute_close_compat_action(
            runtime,
            ticket_id=ticket_id,
            actor_id=actor_id,
            payload=body,
            ticket_trace_id_getter=ticket_trace_id_getter,
        )
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        result_payload = ticket_to_dict(ticket)
        result_payload["approval_required"] = False
        result_payload["event_type"] = action_result["event_type"]
        result_payload["resolved_action"] = action_result["resolved_action"]
        result_payload["trace_id"] = action_result["trace_id"]
        if collab_state is not None:
            result_payload["collab_graph"] = collab_state
        return result_payload
    else:
        raise ValueError(f"unsupported action: {action}")

    result_payload = ticket_to_dict(ticket)
    result_payload["approval_required"] = False
    if collab_state is not None:
        result_payload["collab_graph"] = collab_state
    return result_payload


def execute_action_without_approval(
    runtime: Any,
    *,
    ticket_id: str,
    action: str,
    payload: dict[str, Any],
    ticket_trace_id_getter: Callable[[Any], str | None],
) -> Ticket:
    actor_id = str(payload.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")
    if action == "claim":
        return runtime.ticket_api.assign_ticket(ticket_id, assignee=actor_id, actor_id=actor_id)
    if action == "reassign":
        target_queue = str(payload.get("target_queue") or "").strip()
        target_assignee = str(payload.get("target_assignee") or "").strip()
        updates: dict[str, Any] = {}
        if target_queue:
            updates["queue"] = target_queue
        if updates:
            runtime.ticket_api.update_ticket(ticket_id, updates, actor_id=actor_id)
        ticket = (
            runtime.ticket_api.assign_ticket(ticket_id, assignee=target_assignee, actor_id=actor_id)
            if target_assignee
            else runtime.ticket_api.require_ticket(ticket_id)
        )
        runtime.ticket_api.add_event(
            ticket_id,
            event_type="ticket_reassign_requested",
            actor_type="agent",
            actor_id=actor_id,
            payload={
                "target_queue": target_queue,
                "target_assignee": target_assignee,
                "requested_via": "approval_runtime",
            },
        )
        return ticket
    if action == "escalate":
        note = str(payload.get("note") or "升级处理")
        return runtime.ticket_api.escalate_ticket(ticket_id, actor_id=actor_id, reason=note)
    if action == "resolve":
        execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action="resolve",
            actor_id=actor_id,
            payload=payload,
        )
        return runtime.ticket_api.require_ticket(ticket_id)
    if action in {"customer-confirm", "operator-close"}:
        execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action=action,
            actor_id=actor_id,
            payload=payload,
        )
        return runtime.ticket_api.require_ticket(ticket_id)
    if action == "close":
        execute_close_compat_action(
            runtime,
            ticket_id=ticket_id,
            actor_id=actor_id,
            payload=payload,
            ticket_trace_id_getter=ticket_trace_id_getter,
        )
        return runtime.ticket_api.require_ticket(ticket_id)
    raise ValueError(f"unsupported action: {action}")


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
