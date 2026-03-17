from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.agents.deep.operator_dispatch_agent import (
    DispatchCollaborationAgent,
    OperatorSupervisorAgent,
    build_dispatch_collaboration_agent,
    build_operator_supervisor_agent,
)
from app.agents.deep.ticket_investigation_agent import (
    TicketInvestigationAgent,
    build_ticket_investigation_agent,
    run_ticket_investigation,
)
from app.application.collab_service import (
    CollabService,
    prepare_collab_action_state,
    resume_collab_action_state_from_payload,
)
from app.application.intake_service import IntakeService
from app.bootstrap.runtime import build_ops_api_bootstrap
from app.domain.ticket.ticket_api import TicketAPI as TicketAPIV2
from app.graph_runtime.collab_graph import build_collab_graph
from app.graph_runtime.intake_graph import build_intake_graph
from app.transport.http.handlers import (
    try_handle_approval_action_routes,
    try_handle_channel_routes,
    try_handle_copilot_routes,
    try_handle_kb_routes,
    try_handle_retrieval_and_approval_routes,
    try_handle_session_control_routes,
    try_handle_session_read_routes,
    try_handle_ticket_action_routes,
    try_handle_ticket_read_routes,
    try_handle_trace_routes,
)
from app.transport.http.server import build_http_handler
from config import AppConfig
from core.disambiguation import NewIssueDetector, detect_session_control
from core.hitl.approval_runtime import ApprovalRuntime
from core.hitl.handoff_context import build_approval_context
from core.intent_router import IntentDecision, IntentRouter
from core.recommended_actions_engine import RecommendedActionsEngine
from core.retrieval.source_attribution import build_source_payloads
from core.retriever import Retriever
from core.summary_engine import SummaryEngine
from core.ticket_api import TicketAPI as LegacyTicketAPI
from core.trace_logger import JsonTraceLogger, new_trace_id
from openclaw_adapter.gateway import OpenClawGateway
from runtime.agents import AgentRegistry
from runtime.tools import ToolRegistry
from scripts.dev_reloader import (
    RELOADER_CHILD_ENV,
    build_default_watch_roots,
    run_with_reloader,
)
from scripts.gateway_status import collect_status, summarize_reliability
from storage.models import KBDocument, Ticket
from storage.ticket_repository import TicketRepository
from tools.search_kb import search_kb

DEFAULT_HOST = os.getenv("OPS_API_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("OPS_API_PORT", "18082"))
DEFAULT_ERROR_MESSAGE = "请求处理失败，请稍后重试。"


@dataclass(frozen=True)
class OpsApiRuntime:
    app_config: AppConfig
    gateway: OpenClawGateway
    ticket_api: LegacyTicketAPI
    ticket_api_v2: TicketAPIV2
    repository: TicketRepository
    trace_logger: JsonTraceLogger
    retriever: Retriever
    summary_engine: SummaryEngine
    recommendation_engine: RecommendedActionsEngine
    tool_registry: ToolRegistry
    agent_registry: AgentRegistry
    approval_runtime: ApprovalRuntime
    intake_graph_runner: Any
    investigation_agent: TicketInvestigationAgent
    operator_agent: OperatorSupervisorAgent
    dispatch_agent: DispatchCollaborationAgent
    collab_service: CollabService
    kb_store_path: Path


@dataclass(frozen=True)
class ApiResponse:
    status: HTTPStatus
    payload: dict[str, Any]


def _seed_root() -> Path:
    return Path(__file__).resolve().parents[1] / "seed_data"


def build_runtime(environment: str | None) -> OpsApiRuntime:
    bootstrap = build_ops_api_bootstrap(environment, seed_root=_seed_root())
    kb_store_path = bootstrap.kb_store_path
    if not kb_store_path.exists():
        _write_kb_docs(kb_store_path, _seed_kb_docs())

    investigation_agent = build_ticket_investigation_agent(
        read_ticket_tool=lambda ticket_id: _ticket_to_dict(
            bootstrap.ticket_api.require_ticket(str(ticket_id))
        ),
        read_ticket_events_tool=lambda ticket_id: [
            _event_to_dict(item) for item in bootstrap.ticket_api.list_events(str(ticket_id))
        ],
        search_kb_tool=lambda query: search_kb(
            retriever=bootstrap.retriever,
            source_type="grounded",
            query=str(query),
            top_k=3,
            retrieval_mode=None,
        ),
        search_similar_cases_tool=lambda ticket_id: _extract_similar_cases(
            bootstrap.ticket_api.require_ticket(str(ticket_id)),
            bootstrap.retriever,
        ),
        get_grounding_sources_tool=lambda ticket_id: _extract_grounding_sources(
            bootstrap.ticket_api.require_ticket(str(ticket_id)),
            bootstrap.retriever,
        ),
    )
    intake_graph_runner = build_intake_graph(IntakeService(), investigation_agent)
    collab_service = CollabService(build_collab_graph())
    runtime_ref: dict[str, OpsApiRuntime] = {}
    operator_agent = build_operator_supervisor_agent(
        read_dashboard_summary_tool=lambda: _dashboard_summary(runtime_ref["runtime"]),
        read_queue_summary_tool=lambda: _queue_summary(runtime_ref["runtime"]),
        search_grounding_tool=lambda query: _copilot_grounding_sources(
            runtime_ref["runtime"], str(query), top_k=5
        ),
    )
    dispatch_agent = build_dispatch_collaboration_agent(
        read_queue_summary_tool=lambda: _queue_summary(runtime_ref["runtime"]),
        search_grounding_tool=lambda query: _copilot_grounding_sources(
            runtime_ref["runtime"], str(query), top_k=5
        ),
    )
    runtime = OpsApiRuntime(
        app_config=bootstrap.app_config,
        gateway=bootstrap.gateway,
        ticket_api=bootstrap.ticket_api,
        ticket_api_v2=bootstrap.ticket_api_v2,
        repository=bootstrap.repository,
        trace_logger=bootstrap.trace_logger,
        retriever=bootstrap.retriever,
        summary_engine=bootstrap.summary_engine,
        recommendation_engine=bootstrap.recommendation_engine,
        tool_registry=bootstrap.tool_registry,
        agent_registry=bootstrap.agent_registry,
        approval_runtime=bootstrap.approval_runtime,
        intake_graph_runner=intake_graph_runner,
        investigation_agent=investigation_agent,
        operator_agent=operator_agent,
        dispatch_agent=dispatch_agent,
        collab_service=collab_service,
        kb_store_path=kb_store_path,
    )
    runtime_ref["runtime"] = runtime
    return runtime


def _seed_kb_docs() -> list[dict[str, Any]]:
    docs = Retriever(_seed_root()).search_grounded("工单", top_k=200)
    return [_kb_doc_to_json(item) for item in docs]


def _kb_doc_to_json(doc: KBDocument) -> dict[str, Any]:
    return {
        "doc_id": doc.doc_id,
        "source_type": doc.source_type,
        "title": doc.title,
        "content": doc.content,
        "tags": list(doc.tags),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _load_kb_docs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    docs: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            docs.append(dict(item))
    return docs


def _write_kb_docs(path: Path, docs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")


def _request_id(request_id: str | None) -> str:
    if request_id and request_id.strip():
        return request_id.strip()
    return f"req_{uuid.uuid4().hex[:12]}"


def _error(
    request_id: str,
    *,
    code: str,
    message: str,
    status: HTTPStatus = HTTPStatus.BAD_REQUEST,
    details: dict[str, Any] | None = None,
) -> ApiResponse:
    payload: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details:
        payload["details"] = details
    return ApiResponse(status=status, payload=payload)


def _json_response(
    request_id: str, data: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK
) -> ApiResponse:
    return ApiResponse(status=status, payload={"request_id": request_id, **data})


def _parse_int(value: str | None, *, default: int, minimum: int = 1, maximum: int = 1000) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, min(parsed, maximum))


def _paginate(items: list[dict[str, Any]], *, query: dict[str, str]) -> dict[str, Any]:
    page = _parse_int(query.get("page"), default=1, minimum=1, maximum=100000)
    page_size = _parse_int(query.get("page_size"), default=50, minimum=1, maximum=200)
    start = (page - 1) * page_size
    sliced = items[start : start + page_size]
    return {
        "items": sliced,
        "page": page,
        "page_size": page_size,
        "total": len(items),
    }


def _reliability_snapshot(runtime: OpsApiRuntime) -> dict[str, Any]:
    recent_events = runtime.trace_logger.read_recent(limit=1000)
    session_bindings = runtime.gateway.bindings.session_mapper.list_bindings(limit=500)
    return summarize_reliability(
        recent_events=recent_events,
        session_bindings=session_bindings,
        item_limit=200,
    )


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


def _sla_state(ticket: Ticket) -> str:
    if ticket.resolution_due_at is None:
        return "normal"
    now = datetime.now(UTC)
    due_at = ticket.resolution_due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    if now >= due_at:
        return "breached"
    if due_at - now <= timedelta(hours=2):
        return "warning"
    return "normal"


def _ticket_to_dict(ticket: Ticket) -> dict[str, Any]:
    data = asdict(ticket)
    for key in (
        "created_at",
        "updated_at",
        "first_response_due_at",
        "resolution_due_at",
        "escalated_at",
        "resolved_at",
        "closed_at",
    ):
        value = data.get(key)
        data[key] = value.isoformat() if isinstance(value, datetime) else value
    data["sla_state"] = _sla_state(ticket)
    return data


def _event_to_dict(event: Any) -> dict[str, Any]:
    data = asdict(event)
    if isinstance(data.get("created_at"), datetime):
        data["created_at"] = data["created_at"].isoformat()
    data.setdefault("source", "ticket")
    data.setdefault("trace_id", None)
    return data


def _trace_event_to_dict(event: dict[str, Any], *, ticket_id: str, index: int) -> dict[str, Any]:
    payload_raw = event.get("payload")
    payload = dict(payload_raw) if isinstance(payload_raw, dict) else {}
    trace_id = event.get("trace_id")
    trace_id_text = str(trace_id) if trace_id else None
    session_id = event.get("session_id")
    session_id_text = str(session_id) if session_id else None

    if trace_id_text and "trace_id" not in payload:
        payload["trace_id"] = trace_id_text
    if session_id_text and "session_id" not in payload:
        payload["session_id"] = session_id_text

    event_type = str(event.get("event_type") or "trace_event")
    event_id = f"trace_evt_{trace_id_text or ticket_id}_{index}"
    created_at_raw = event.get("timestamp")
    created_at = str(created_at_raw) if created_at_raw else None

    return {
        "event_id": event_id,
        "ticket_id": str(event.get("ticket_id") or ticket_id),
        "event_type": event_type,
        "actor_type": "trace",
        "actor_id": session_id_text or trace_id_text or "trace-logger",
        "payload": payload,
        "created_at": created_at,
        "source": "trace",
        "trace_id": trace_id_text,
    }


def _event_sort_key(item: dict[str, Any]) -> tuple[datetime, str]:
    created_at = item.get("created_at")
    parsed = _parse_iso_datetime(str(created_at)) if created_at else None
    if parsed is None:
        parsed = datetime.min.replace(tzinfo=UTC)
    return (parsed, str(item.get("event_id", "")))


def _ticket_timeline_events(runtime: OpsApiRuntime, ticket_id: str) -> list[dict[str, Any]]:
    timeline = [_event_to_dict(item) for item in runtime.ticket_api.list_events(ticket_id)]
    trace_events = runtime.trace_logger.query_by_ticket(ticket_id, limit=500)
    for index, item in enumerate(trace_events):
        if not isinstance(item, dict):
            continue
        timeline.append(_trace_event_to_dict(item, ticket_id=ticket_id, index=index))
    timeline.sort(key=_event_sort_key)
    return timeline


def _reply_event_to_dict(event: dict[str, Any], *, index: int) -> dict[str, Any]:
    payload_raw = event.get("payload")
    payload = dict(payload_raw) if isinstance(payload_raw, dict) else {}
    llm_trace = _normalize_llm_trace(payload)
    trace_id = event.get("trace_id")
    ticket_id = event.get("ticket_id")
    session_id = event.get("session_id")
    trace_id_text = str(trace_id) if trace_id else None
    ticket_id_text = str(ticket_id) if ticket_id else None
    session_id_text = str(session_id) if session_id else None
    created_at_raw = event.get("timestamp")
    created_at = str(created_at_raw) if created_at_raw else None
    generation_type = str(payload["generation_type"]) if payload.get("generation_type") else None
    tone = str(payload["tone"]) if payload.get("tone") else None
    workflow = str(payload["workflow"]) if payload.get("workflow") else None
    reply_preview = str(payload["reply_preview"]) if payload.get("reply_preview") else None
    grounding_sources = [
        str(item) for item in payload.get("grounding_sources", []) if isinstance(item, str)
    ]
    fallback_key = trace_id_text or ticket_id_text or session_id_text or "unknown"
    return {
        "event_id": f"reply_evt_{fallback_key}_{index}",
        "event_type": "reply_generated",
        "trace_id": trace_id_text,
        "ticket_id": ticket_id_text,
        "session_id": session_id_text,
        "created_at": created_at,
        "source": "trace",
        "provider": llm_trace.get("provider"),
        "model": llm_trace.get("model"),
        "prompt_key": llm_trace.get("prompt_key"),
        "prompt_version": llm_trace.get("prompt_version"),
        "request_id": llm_trace.get("request_id"),
        "token_usage": llm_trace.get("token_usage"),
        "retry_count": llm_trace.get("retry_count"),
        "success": llm_trace.get("success"),
        "error": llm_trace.get("error"),
        "fallback_used": llm_trace.get("fallback_used"),
        "degraded": llm_trace.get("degraded"),
        "degrade_reason": llm_trace.get("degrade_reason"),
        "generation_type": generation_type,
        "tone": tone,
        "workflow": workflow,
        "reply_preview": reply_preview,
        "grounding_sources": grounding_sources,
        "payload": payload,
    }


def _ticket_reply_events(runtime: OpsApiRuntime, ticket_id: str) -> list[dict[str, Any]]:
    events = runtime.trace_logger.query_by_ticket(ticket_id, limit=1000)
    items: list[dict[str, Any]] = []
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            continue
        if str(item.get("event_type") or "") != "reply_generated":
            continue
        items.append(_reply_event_to_dict(item, index=index))
    items.sort(key=_event_sort_key)
    return items


def _session_reply_events(runtime: OpsApiRuntime, session_id: str) -> list[dict[str, Any]]:
    events = runtime.trace_logger.query_by_session(session_id, limit=1000)
    items: list[dict[str, Any]] = []
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            continue
        if str(item.get("event_type") or "") != "reply_generated":
            continue
        items.append(_reply_event_to_dict(item, index=index))
    items.sort(key=_event_sort_key)
    return items


def _ticket_trace_id(ticket: Ticket) -> str | None:
    raw = ticket.metadata.get("trace_id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _ticket_duplicate_candidates(runtime: OpsApiRuntime, ticket_id: str) -> list[dict[str, Any]]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    trace_id = _ticket_trace_id(ticket) or new_trace_id()
    items = runtime.ticket_api.list_duplicate_candidates(ticket_id, limit=5)
    payload = {
        "ticket_id": ticket_id,
        "candidate_count": len(items),
        "candidate_ticket_ids": [
            str(item.get("ticket_id") or "") for item in items if item.get("ticket_id")
        ],
    }
    runtime.ticket_api.add_event(
        ticket_id,
        event_type="duplicate_candidates_generated",
        actor_type="agent",
        actor_id="ops-api",
        payload=payload,
    )
    runtime.trace_logger.log(
        "duplicate_candidates_generated",
        payload,
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    return items


def _merge_suggestion_decision(
    runtime: OpsApiRuntime,
    *,
    ticket_id: str,
    decision: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    actor_id = str(payload.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")
    target_ticket_id = str(
        payload.get("duplicate_ticket_id") or payload.get("target_ticket_id") or ""
    ).strip()
    if not target_ticket_id:
        raise ValueError("duplicate_ticket_id is required")
    note = str(payload.get("note") or "").strip() or None

    source_ticket = runtime.ticket_api.require_ticket(ticket_id)
    trace_id = str(
        payload.get("trace_id") or _ticket_trace_id(source_ticket) or new_trace_id()
    ).strip()
    if decision == "accept":
        updated_ticket = runtime.ticket_api.accept_merge_suggestion(
            ticket_id,
            target_ticket_id=target_ticket_id,
            actor_id=actor_id,
            trace_id=trace_id,
            note=note,
        )
        event_type = "merge_suggestion_accepted"
    elif decision == "reject":
        updated_ticket = runtime.ticket_api.reject_merge_suggestion(
            ticket_id,
            target_ticket_id=target_ticket_id,
            actor_id=actor_id,
            trace_id=trace_id,
            note=note,
        )
        event_type = "merge_suggestion_rejected"
    else:
        raise ValueError(f"unsupported merge decision: {decision}")

    runtime.trace_logger.log(
        event_type,
        {
            "decision": decision,
            "source_ticket_id": ticket_id,
            "target_ticket_id": target_ticket_id,
            "actor_id": actor_id,
            "note": note,
        },
        trace_id=trace_id,
        ticket_id=ticket_id,
        session_id=updated_ticket.session_id,
    )
    return {
        "data": _ticket_to_dict(updated_ticket),
        "decision": decision,
        "target_ticket_id": target_ticket_id,
        "trace_id": trace_id,
    }


def _session_payload(runtime: OpsApiRuntime, session_id: str) -> dict[str, Any] | None:
    binding = runtime.gateway.bindings.session_mapper.get(session_id)
    if binding is None:
        return None
    session_context = runtime.gateway.bindings.session_mapper.get_session_context(session_id)
    active_ticket_id = (
        str(session_context.get("active_ticket_id") or binding.ticket_id or "").strip() or None
    )
    recent_ticket_ids = [
        str(item).strip()
        for item in session_context.get("recent_ticket_ids", [])
        if str(item).strip()
    ]
    if active_ticket_id:
        recent_ticket_ids = [item for item in recent_ticket_ids if item != active_ticket_id]
    return {
        "session_id": binding.session_id,
        "thread_id": binding.thread_id,
        "active_ticket_id": active_ticket_id,
        "recent_ticket_ids": recent_ticket_ids,
        "session_mode": session_context.get("session_mode"),
        "last_intent": session_context.get("last_intent"),
        "updated_at": session_context.get("updated_at")
        or (binding.updated_at.isoformat() if binding.updated_at else None),
        "metadata": dict(binding.metadata),
    }


def _session_ticket_list(runtime: OpsApiRuntime, session_id: str) -> list[dict[str, Any]]:
    binding = runtime.gateway.bindings.session_mapper.get(session_id)
    if binding is None:
        return []
    session_tickets = [
        ticket
        for ticket in runtime.repository.list_tickets(limit=2000, offset=0)
        if ticket.session_id == session_id
    ]
    by_ticket_id = {ticket.ticket_id: ticket for ticket in session_tickets}
    ordered_ids = runtime.gateway.bindings.session_mapper.list_session_ticket_ids(
        session_id,
        include_active=True,
        include_recent=True,
        limit=50,
    )
    ordered: list[Ticket] = []
    seen: set[str] = set()
    for ticket_id in ordered_ids:
        ticket = by_ticket_id.get(ticket_id)
        if ticket is None or ticket.ticket_id in seen:
            continue
        ordered.append(ticket)
        seen.add(ticket.ticket_id)
    min_dt = datetime.min.replace(tzinfo=UTC)
    for ticket in sorted(session_tickets, key=lambda item: item.updated_at or min_dt, reverse=True):
        if ticket.ticket_id in seen:
            continue
        ordered.append(ticket)
        seen.add(ticket.ticket_id)
    return [_ticket_to_dict(ticket) for ticket in ordered]


def _disambiguation_options(
    *,
    session_id: str,
    active_ticket_id: str | None,
    candidate_ticket_ids: list[str],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if active_ticket_id:
        options.append(
            {
                "action": "continue_current",
                "ticket_id": active_ticket_id,
                "label": f"继续当前工单（{active_ticket_id}）",
                "endpoint": f"/api/tickets/{active_ticket_id}/switch-active",
                "method": "POST",
                "payload": {"session_id": session_id},
            }
        )
    options.append(
        {
            "action": "create_new",
            "label": "按新问题处理",
            "endpoint": f"/api/sessions/{session_id}/new-issue",
            "method": "POST",
            "payload": {},
        }
    )
    for ticket_id in candidate_ticket_ids:
        if ticket_id == active_ticket_id:
            continue
        options.append(
            {
                "action": "switch_ticket",
                "ticket_id": ticket_id,
                "label": f"切换到工单 {ticket_id}",
                "endpoint": f"/api/tickets/{ticket_id}/switch-active",
                "method": "POST",
                "payload": {"session_id": session_id},
            }
        )
    return options


def _copilot_disambiguate_payload(
    runtime: OpsApiRuntime,
    *,
    session_id: str,
    message_text: str,
    actor_id: str = "ops-api",
    trace_id: str | None = None,
) -> dict[str, Any]:
    binding = runtime.gateway.bindings.session_mapper.get(session_id)
    if binding is None:
        raise KeyError(session_id)
    session_context = runtime.gateway.bindings.session_mapper.get_session_context(session_id)
    active_ticket_id = (
        str(session_context.get("active_ticket_id") or "").strip()
        or str(binding.ticket_id or "").strip()
        or None
    )
    candidate_ticket_ids = runtime.gateway.bindings.session_mapper.list_session_ticket_ids(
        session_id,
        include_active=True,
        include_recent=True,
        limit=10,
    )
    active_ticket = runtime.ticket_api.get_ticket(active_ticket_id) if active_ticket_id else None
    intent = IntentRouter().route(message_text)
    decision = NewIssueDetector().evaluate(
        message_text=message_text,
        intent=intent,
        candidate_ticket_ids=candidate_ticket_ids,
        active_ticket_id=active_ticket_id,
        requested_ticket_id=None,
        session_mode=str(session_context.get("session_mode") or "").strip() or None,
        last_intent=str(session_context.get("last_intent") or "").strip() or None,
        active_ticket=active_ticket,
    )

    session_action_result: dict[str, Any] | None = None
    if decision.session_action == "session_end":
        session_action_result = _run_session_end_v2(
            runtime,
            session_id=session_id,
            payload={
                "actor_id": actor_id,
                "reason": "user_requested_end",
                "trace_id": trace_id or new_trace_id(),
            },
        )
    elif decision.session_action == "new_issue":
        session_action_result = _run_session_new_issue(
            runtime,
            session_id=session_id,
            payload={
                "actor_id": actor_id,
                "reason": "user_requested_new_issue",
                "trace_id": trace_id or new_trace_id(),
            },
        )
    elif decision.decision == "awaiting_disambiguation" and decision.active_ticket_id:
        runtime.ticket_api.switch_active_session_ticket(
            session_id,
            decision.active_ticket_id,
            metadata={
                "session_mode": "awaiting_disambiguation",
                "last_intent": decision.intent.intent,
            },
        )
    updated_session = _session_payload(runtime, session_id)
    if updated_session is None:
        raise KeyError(session_id)
    candidate_tickets: list[dict[str, Any]] = []
    for ticket_id in decision.candidate_ticket_ids:
        ticket = runtime.ticket_api.get_ticket(ticket_id)
        if ticket is None:
            continue
        candidate_tickets.append(
            {
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "status": ticket.status,
                "intent": ticket.intent,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            }
        )
    resolved_active_ticket_id = str(updated_session.get("active_ticket_id") or "").strip() or None
    return {
        "session_id": session_id,
        "message_text": message_text,
        "decision": decision.decision,
        "confidence": decision.confidence,
        "reason": decision.reason,
        "session_action": decision.session_action,
        "intent": {
            "intent": decision.intent.intent,
            "confidence": decision.intent.confidence,
            "is_low_confidence": decision.intent.is_low_confidence,
            "reason": decision.intent.reason,
        },
        "suggested_ticket_id": decision.suggested_ticket_id,
        "active_ticket_id": resolved_active_ticket_id,
        "candidate_tickets": candidate_tickets,
        "options": _disambiguation_options(
            session_id=session_id,
            active_ticket_id=resolved_active_ticket_id,
            candidate_ticket_ids=list(decision.candidate_ticket_ids),
        ),
        "session_action_result": session_action_result,
        "session": updated_session,
    }


def _filter_tickets(runtime: OpsApiRuntime, query: dict[str, str]) -> list[Ticket]:
    page_size = _parse_int(query.get("page_size"), default=20, minimum=1, maximum=200)
    scan_limit = max(500, page_size * 50)
    tickets = runtime.repository.list_tickets(limit=scan_limit, offset=0)
    custom_field_aliases: dict[str, tuple[str, ...]] = {
        "service_type": ("service_type",),
        "community": ("community_name", "community"),
        "community_name": ("community_name", "community"),
        "building": ("building",),
        "unit": ("unit",),
        "parking": ("parking_lot", "parking_space_id", "parking"),
        "parking_lot": ("parking_lot",),
        "parking_space_id": ("parking_space_id",),
        "rent_contract_id": ("rent_contract_id",),
        "complaint_category": ("complaint_category",),
        "visit_required": ("visit_required",),
        "follow_up_required": ("follow_up_required",),
        "approval": ("approval_required", "approval"),
        "approval_required": ("approval_required", "approval"),
    }

    def match(ticket: Ticket) -> bool:
        q = (query.get("q") or "").strip().lower()
        if q and q not in f"{ticket.title} {ticket.latest_message}".lower():
            return False
        if query.get("status") and ticket.status != query["status"]:
            return False
        if query.get("queue") and ticket.queue != query["queue"]:
            return False
        if query.get("assignee") and (ticket.assignee or "") != query["assignee"]:
            return False
        if query.get("priority") and ticket.priority != query["priority"]:
            return False
        if query.get("channel") and ticket.channel != query["channel"]:
            return False
        if query.get("handoff_state") and ticket.handoff_state != query["handoff_state"]:
            return False
        if query.get("risk_level") and ticket.risk_level != query["risk_level"]:
            return False
        for query_key, metadata_keys in custom_field_aliases.items():
            expected = query.get(query_key)
            if not expected:
                continue
            if not any(str(ticket.metadata.get(item, "")) == expected for item in metadata_keys):
                return False
        if query.get("sla_state") and _sla_state(ticket) != query["sla_state"]:
            return False

        created_from = _parse_iso_datetime(query.get("created_from"))
        created_to = _parse_iso_datetime(query.get("created_to"))
        if created_from and ticket.created_at and ticket.created_at < created_from:
            return False
        if created_to and ticket.created_at and ticket.created_at > created_to:
            return False
        return True

    filtered = [item for item in tickets if match(item)]

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    sort_by = (query.get("sort_by") or "created_at").strip()
    sort_order = (query.get("sort_order") or "desc").strip().lower()
    reverse = sort_order != "asc"

    def sort_key(ticket: Ticket) -> Any:
        if sort_by == "priority":
            return priority_order.get(str(ticket.priority), 99)
        if sort_by == "status":
            return str(ticket.status)
        if sort_by == "updated_at":
            value = ticket.updated_at
            return value or datetime.min.replace(tzinfo=UTC)
        if sort_by == "risk_level":
            risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            return risk_order.get(str(ticket.risk_level), 1)
        value = ticket.created_at
        return value or datetime.min.replace(tzinfo=UTC)

    filtered.sort(key=sort_key, reverse=reverse)
    return filtered


def _dashboard_summary(runtime: OpsApiRuntime) -> dict[str, Any]:
    tickets = runtime.repository.list_tickets(limit=2000, offset=0)
    recent_events = runtime.trace_logger.read_recent(limit=5000)
    today = datetime.now(UTC).date()

    new_tickets_today = 0
    in_progress_count = 0
    handoff_pending_count = 0
    escalated_count = 0
    sla_warning_count = 0
    sla_breached_count = 0

    for ticket in tickets:
        if ticket.created_at and ticket.created_at.date() == today:
            new_tickets_today += 1
        if ticket.status in {"open", "pending"}:
            in_progress_count += 1
        if ticket.handoff_state in {"requested", "accepted"}:
            handoff_pending_count += 1
        if ticket.status == "escalated":
            escalated_count += 1
        state = _sla_state(ticket)
        if state == "warning":
            sla_warning_count += 1
        elif state == "breached":
            sla_breached_count += 1

    consulting_reuse_count = sum(
        1
        for event in recent_events
        if str(event.get("event_type") or "") == "consulting_ticket_reused"
    )
    duplicate_candidates_count = sum(
        1
        for event in recent_events
        if str(event.get("event_type") or "") == "duplicate_candidates_generated"
    )
    merge_accept_count = sum(
        1
        for event in recent_events
        if str(event.get("event_type") or "") == "merge_suggestion_accepted"
    )
    merge_reject_count = sum(
        1
        for event in recent_events
        if str(event.get("event_type") or "") == "merge_suggestion_rejected"
    )
    merge_decisions = merge_accept_count + merge_reject_count
    merge_accept_rate = round((merge_accept_count / merge_decisions), 4) if merge_decisions else 0.0

    return {
        "new_tickets_today": new_tickets_today,
        "in_progress_count": in_progress_count,
        "handoff_pending_count": handoff_pending_count,
        "escalated_count": escalated_count,
        "sla_warning_count": sla_warning_count,
        "sla_breached_count": sla_breached_count,
        "consulting_reuse_count": consulting_reuse_count,
        "duplicate_candidates_count": duplicate_candidates_count,
        "merge_accept_count": merge_accept_count,
        "merge_reject_count": merge_reject_count,
        "merge_accept_rate": merge_accept_rate,
    }


def _dashboard_recent_errors(runtime: OpsApiRuntime) -> list[dict[str, Any]]:
    events = runtime.trace_logger.read_recent(limit=300)
    failures: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type", ""))
        payload = event.get("payload")
        payload_dict = payload if isinstance(payload, dict) else {}
        if event_type.endswith("failed") or "error" in payload_dict:
            failures.append(
                {
                    "timestamp": event.get("timestamp"),
                    "trace_id": event.get("trace_id"),
                    "ticket_id": event.get("ticket_id"),
                    "event_type": event_type,
                    "error": payload_dict.get("error"),
                }
            )
    return failures[-50:]


def _trace_groups(runtime: OpsApiRuntime) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in runtime.trace_logger.read_recent(limit=5000):
        trace_id = str(event.get("trace_id") or "")
        if not trace_id:
            continue
        groups.setdefault(trace_id, []).append(event)
    return groups


def _trace_summary(
    runtime: OpsApiRuntime, trace_id: str, events: list[dict[str, Any]]
) -> dict[str, Any]:
    first = events[0]
    last = events[-1]
    first_ts = _parse_iso_datetime(str(first.get("timestamp", "")))
    last_ts = _parse_iso_datetime(str(last.get("timestamp", "")))
    latency_ms: int | None = None
    if first_ts and last_ts:
        latency_ms = int((last_ts - first_ts).total_seconds() * 1000)

    route_decision = {}
    handoff_reason = None
    channel = None
    provider = runtime.app_config.llm.provider
    model: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    request_id: str | None = None
    token_usage: dict[str, Any] | None = None
    retry_count: int | None = None
    llm_success: bool | None = None
    llm_error: str | None = None
    fallback_used = False
    degraded = False
    degrade_reason: str | None = None
    generation_type: str | None = None
    workflow = "support-intake"
    error_only = False
    handoff = False
    ticket_id = None
    session_id = None

    for item in events:
        payload = item.get("payload")
        payload_dict = payload if isinstance(payload, dict) else {}
        event_type = str(item.get("event_type", ""))
        if ticket_id is None and item.get("ticket_id"):
            ticket_id = item.get("ticket_id")
        if session_id is None and item.get("session_id"):
            session_id = item.get("session_id")
        if event_type == "route_decision":
            route_decision = payload_dict
        if event_type == "handoff_decision" and payload_dict.get("should_handoff"):
            handoff = True
            handoff_reason = str(payload_dict.get("reason", ""))
        if "channel" in payload_dict and channel is None:
            channel = str(payload_dict["channel"])
        if "provider" in payload_dict:
            provider = str(payload_dict["provider"])
        if "model" in payload_dict and isinstance(payload_dict.get("model"), str):
            model = str(payload_dict["model"])
        if "prompt_key" in payload_dict and isinstance(payload_dict.get("prompt_key"), str):
            prompt_key = str(payload_dict["prompt_key"])
        if "prompt_version" in payload_dict and isinstance(payload_dict.get("prompt_version"), str):
            prompt_version = str(payload_dict["prompt_version"])
        if "request_id" in payload_dict and payload_dict.get("request_id") is not None:
            request_id = str(payload_dict["request_id"])
        if "token_usage" in payload_dict and isinstance(payload_dict.get("token_usage"), dict):
            token_usage = dict(payload_dict["token_usage"])
        if "retry_count" in payload_dict:
            parsed_retry = _coerce_int(payload_dict.get("retry_count"))
            if parsed_retry is not None:
                retry_count = parsed_retry
        if "success" in payload_dict:
            llm_success = bool(payload_dict["success"])
        if "error" in payload_dict and payload_dict.get("error"):
            llm_error = str(payload_dict["error"])
        if "fallback_used" in payload_dict:
            fallback_used = bool(payload_dict["fallback_used"])
        if "degraded" in payload_dict:
            degraded = bool(payload_dict["degraded"])
        if "degrade_reason" in payload_dict and payload_dict.get("degrade_reason"):
            degrade_reason = str(payload_dict["degrade_reason"])
        if "generation_type" in payload_dict and payload_dict.get("generation_type"):
            generation_type = str(payload_dict["generation_type"])
        if "workflow" in payload_dict:
            workflow = str(payload_dict["workflow"])
        if event_type.endswith("failed") or "error" in payload_dict:
            error_only = True

    return {
        "trace_id": trace_id,
        "ticket_id": ticket_id,
        "session_id": session_id,
        "workflow": workflow,
        "channel": channel,
        "provider": provider,
        "model": model,
        "prompt_key": prompt_key,
        "prompt_version": prompt_version,
        "request_id": request_id,
        "token_usage": token_usage,
        "retry_count": retry_count,
        "success": llm_success,
        "error": llm_error,
        "fallback_used": fallback_used,
        "degraded": degraded,
        "degrade_reason": degrade_reason,
        "generation_type": generation_type,
        "route_decision": route_decision,
        "handoff": handoff,
        "handoff_reason": handoff_reason,
        "error_only": error_only,
        "latency_ms": latency_ms,
        "created_at": first.get("timestamp"),
    }


def _trace_detail_event_to_dict(event: dict[str, Any], *, index: int) -> dict[str, Any]:
    payload_raw = event.get("payload")
    payload = payload_raw if isinstance(payload_raw, dict) else {}
    trace_id = event.get("trace_id")
    trace_id_text = str(trace_id) if trace_id else ""
    return {
        "event_id": f"trace_evt_{trace_id_text}_{index}",
        "event_type": str(event.get("event_type") or "trace_event"),
        "timestamp": event.get("timestamp"),
        "ticket_id": event.get("ticket_id"),
        "session_id": event.get("session_id"),
        "payload": payload,
    }


def _queue_summary(runtime: OpsApiRuntime) -> list[dict[str, Any]]:
    tickets = runtime.repository.list_tickets(limit=3000, offset=0)
    summary: dict[str, dict[str, Any]] = {}
    for ticket in tickets:
        bucket = summary.setdefault(
            ticket.queue,
            {
                "queue_name": ticket.queue,
                "open_count": 0,
                "in_progress_count": 0,
                "warning_count": 0,
                "breached_count": 0,
                "escalated_count": 0,
                "assignees": set(),
            },
        )
        if ticket.status == "open":
            bucket["open_count"] += 1
        if ticket.status in {"pending", "escalated"}:
            bucket["in_progress_count"] += 1
        if ticket.status == "escalated":
            bucket["escalated_count"] += 1
        state = _sla_state(ticket)
        if state == "warning":
            bucket["warning_count"] += 1
        elif state == "breached":
            bucket["breached_count"] += 1
        if ticket.assignee:
            bucket["assignees"].add(ticket.assignee)

    rows: list[dict[str, Any]] = []
    for queue_name, bucket in summary.items():
        rows.append(
            {
                "queue_name": queue_name,
                "open_count": bucket["open_count"],
                "in_progress_count": bucket["in_progress_count"],
                "warning_count": bucket["warning_count"],
                "breached_count": bucket["breached_count"],
                "escalated_count": bucket["escalated_count"],
                "assignee_count": len(bucket["assignees"]),
            }
        )
    rows.sort(key=lambda item: str(item["queue_name"]))
    return rows


def _extract_similar_cases(ticket: Ticket, retriever: Retriever) -> list[dict[str, Any]]:
    metadata_cases = ticket.metadata.get("similar_cases")
    if isinstance(metadata_cases, list):
        cases: list[dict[str, Any]] = []
        for item in metadata_cases:
            if isinstance(item, dict):
                cases.append(dict(item))
        if cases:
            return cases[:10]

    detailed = retriever.search_with_details(
        "history_case",
        ticket.latest_message,
        top_k=5,
        mode="hybrid",
    )
    attributions = build_source_payloads(ticket.latest_message, detailed, top_k=5)
    return [
        {
            "doc_id": item["source_id"],
            "source_id": item["source_id"],
            "source_type": item["source_type"],
            "title": item["title"],
            "score": item["score"],
            "rank": item["rank"],
            "reason": item["reason"],
            "snippet": item["snippet"],
            "retrieval_mode": item["retrieval_mode"],
        }
        for item in attributions
    ]


def _extract_grounding_sources(ticket: Ticket, retriever: Retriever) -> list[dict[str, Any]]:
    metadata_sources = ticket.metadata.get("grounding_sources")
    if isinstance(metadata_sources, list):
        sources: list[dict[str, Any]] = []
        for item in metadata_sources:
            if isinstance(item, dict):
                sources.append(dict(item))
        if sources:
            return sources[:10]

    detailed = retriever.search_grounded_with_details(
        ticket.latest_message,
        top_k=5,
        mode="hybrid",
    )
    return build_source_payloads(ticket.latest_message, detailed, top_k=5)


def _require_copilot_query(
    request_id: str, payload: dict[str, Any]
) -> tuple[str | None, ApiResponse | None]:
    query_text = str(payload.get("query") or "").strip()
    if query_text:
        return query_text, None
    return None, _error(
        request_id,
        code="invalid_payload",
        message="query is required",
        status=HTTPStatus.BAD_REQUEST,
    )


def _default_copilot_llm_trace(scope: str) -> dict[str, Any]:
    return {
        "provider": "fallback",
        "model": None,
        "prompt_key": f"copilot_{scope}_query",
        "prompt_version": "v1",
        "latency_ms": None,
        "request_id": None,
        "token_usage": None,
        "retry_count": 0,
        "success": True,
        "error": None,
        "fallback_used": True,
        "degraded": False,
        "degrade_reason": None,
    }


def _copilot_grounding_sources(
    runtime: OpsApiRuntime, query_text: str, *, top_k: int = 5
) -> list[dict[str, Any]]:
    detailed = runtime.retriever.search_grounded_with_details(
        query_text, top_k=top_k, mode="hybrid"
    )
    return build_source_payloads(query_text, detailed, top_k=top_k)


def _build_copilot_operator_payload(runtime: OpsApiRuntime, query_text: str) -> dict[str, Any]:
    payload = dict(runtime.operator_agent.analyze(query_text, actor_id="copilot-operator"))
    grounding_sources = payload.get("grounding_sources")
    if not isinstance(grounding_sources, list):
        grounding_sources = []
        payload["grounding_sources"] = grounding_sources
    risk_flags = payload.get("risk_flags")
    if isinstance(risk_flags, list):
        normalized_risk_flags = [str(item) for item in risk_flags if str(item)]
    else:
        normalized_risk_flags = []
    if not grounding_sources:
        normalized_risk_flags = sorted({*normalized_risk_flags, "low_grounding"})
    payload["scope"] = "operator"
    payload["query"] = query_text
    payload["risk_flags"] = normalized_risk_flags
    payload.setdefault("llm_trace", _default_copilot_llm_trace("operator"))
    payload.setdefault("generated_at", datetime.now(UTC).isoformat())
    return payload


def _build_copilot_queue_payload(
    runtime: OpsApiRuntime, query_text: str, *, queue_name: str | None = None
) -> dict[str, Any]:
    rows = _queue_summary(runtime)
    if queue_name:
        rows = [item for item in rows if str(item.get("queue_name")) == queue_name]
    ranked = sorted(
        rows,
        key=lambda item: (
            int(item.get("breached_count", 0)),
            int(item.get("warning_count", 0)),
            int(item.get("escalated_count", 0)),
            int(item.get("in_progress_count", 0)),
        ),
        reverse=True,
    )
    focus = ranked[0] if ranked else None
    focus_queue = str(focus.get("queue_name")) if focus else queue_name or "n/a"
    answer = (
        f"Queue建议：优先关注队列 {focus_queue}。" if focus else "Queue建议：当前无可分析队列数据。"
    )
    grounding_sources = _copilot_grounding_sources(runtime, query_text, top_k=5)
    risk_flags = ["low_grounding"] if not grounding_sources else []
    return {
        "scope": "queue",
        "query": query_text,
        "queue_name": focus_queue,
        "answer": answer,
        "queue_summary": ranked[:10],
        "grounding_sources": grounding_sources,
        "risk_flags": risk_flags,
        "llm_trace": _default_copilot_llm_trace("queue"),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _build_copilot_ticket_payload(
    runtime: OpsApiRuntime, ticket: Ticket, query_text: str
) -> dict[str, Any]:
    events = runtime.ticket_api.list_events(ticket.ticket_id)
    summary = runtime.summary_engine.case_summary(ticket, events)
    llm_trace = _normalize_llm_trace(runtime.summary_engine.last_generation_metadata())
    grounding_sources = _extract_grounding_sources(ticket, runtime.retriever)
    metadata_risk_flags = ticket.metadata.get("risk_flags")
    risk_flags = (
        [str(item) for item in metadata_risk_flags if isinstance(item, str)]
        if isinstance(metadata_risk_flags, list)
        else []
    )
    if not grounding_sources:
        risk_flags = sorted({*risk_flags, "low_grounding"})
    answer = f"{summary} 结合问题“{query_text}”，建议按推荐动作逐项执行并同步客户进度。"
    return {
        "scope": "ticket",
        "query": query_text,
        "ticket_id": ticket.ticket_id,
        "answer": answer,
        "summary": summary,
        "grounding_sources": grounding_sources,
        "risk_flags": risk_flags,
        "llm_trace": llm_trace,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _build_copilot_dispatch_payload(runtime: OpsApiRuntime, query_text: str) -> dict[str, Any]:
    payload = dict(runtime.dispatch_agent.analyze(query_text, actor_id="copilot-dispatch"))
    grounding_sources = payload.get("grounding_sources")
    if not isinstance(grounding_sources, list):
        grounding_sources = []
        payload["grounding_sources"] = grounding_sources
    risk_flags = payload.get("risk_flags")
    if isinstance(risk_flags, list):
        normalized_risk_flags = [str(item) for item in risk_flags if str(item)]
    else:
        normalized_risk_flags = []
    if not grounding_sources:
        normalized_risk_flags = sorted({*normalized_risk_flags, "low_grounding"})
    payload["scope"] = "dispatch"
    payload["query"] = query_text
    payload["risk_flags"] = normalized_risk_flags
    payload.setdefault("llm_trace", _default_copilot_llm_trace("dispatch"))
    payload.setdefault("generated_at", datetime.now(UTC).isoformat())
    return payload


def _retrieval_health_payload(runtime: OpsApiRuntime) -> dict[str, Any]:
    return {
        "status": "ok",
        "modes": ["lexical", "vector", "hybrid"],
        "sources": runtime.retriever.source_stats(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _extract_llm_trace_for_ticket(runtime: OpsApiRuntime, ticket: Ticket) -> dict[str, Any]:
    metadata_trace = ticket.metadata.get("llm_trace")
    if isinstance(metadata_trace, dict):
        normalized = _normalize_llm_trace(metadata_trace)
        if normalized:
            return normalized

    latest_summary_event = runtime.trace_logger.latest_by_ticket(
        ticket.ticket_id, event_type="summary_generated"
    )
    if latest_summary_event and isinstance(latest_summary_event.get("payload"), dict):
        normalized = _normalize_llm_trace(latest_summary_event["payload"])
        if normalized:
            return normalized

    return _normalize_llm_trace({})


def _normalize_llm_trace(raw: dict[str, Any]) -> dict[str, Any]:
    token_usage = raw.get("token_usage")
    return {
        "provider": str(raw.get("provider") or "fallback"),
        "model": str(raw["model"]) if isinstance(raw.get("model"), str) else None,
        "prompt_key": str(raw["prompt_key"]) if isinstance(raw.get("prompt_key"), str) else None,
        "prompt_version": (
            str(raw["prompt_version"]) if isinstance(raw.get("prompt_version"), str) else None
        ),
        "latency_ms": _coerce_int(raw.get("latency_ms")),
        "request_id": str(raw["request_id"]) if isinstance(raw.get("request_id"), str) else None,
        "token_usage": dict(token_usage) if isinstance(token_usage, dict) else None,
        "retry_count": _coerce_int(raw.get("retry_count")) or 0,
        "success": bool(raw.get("success", False)),
        "error": str(raw["error"]) if raw.get("error") else None,
        "fallback_used": bool(raw.get("fallback_used", False)),
        "degraded": bool(raw.get("degraded", False)),
        "degrade_reason": str(raw["degrade_reason"]) if raw.get("degrade_reason") else None,
    }


def _coerce_int(raw: object) -> int | None:
    if isinstance(raw, int):
        return raw
    if raw is None:
        return None
    try:
        return int(str(raw))
    except ValueError:
        return None


def _resolve_action(
    runtime: OpsApiRuntime, *, ticket_id: str, action: str, body: dict[str, Any]
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
        ticket_payload = _ticket_to_dict(approval_result.ticket)
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
        action_result = _execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action="resolve",
            actor_id=actor_id,
            payload=body,
        )
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        payload = _ticket_to_dict(ticket)
        payload["approval_required"] = False
        payload["event_type"] = action_result["event_type"]
        payload["resolved_action"] = action_result["resolved_action"]
        payload["trace_id"] = action_result["trace_id"]
        if collab_state is not None:
            payload["collab_graph"] = collab_state
        return payload
    elif action in {"customer-confirm", "operator-close"}:
        action_result = _execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action=action,
            actor_id=actor_id,
            payload=body,
        )
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        payload = _ticket_to_dict(ticket)
        payload["approval_required"] = False
        payload["event_type"] = action_result["event_type"]
        payload["resolved_action"] = action_result["resolved_action"]
        payload["trace_id"] = action_result["trace_id"]
        if collab_state is not None:
            payload["collab_graph"] = collab_state
        return payload
    elif action == "close":
        action_result = _execute_close_compat_action(
            runtime,
            ticket_id=ticket_id,
            actor_id=actor_id,
            payload=body,
        )
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        payload = _ticket_to_dict(ticket)
        payload["approval_required"] = False
        payload["event_type"] = action_result["event_type"]
        payload["resolved_action"] = action_result["resolved_action"]
        payload["trace_id"] = action_result["trace_id"]
        if collab_state is not None:
            payload["collab_graph"] = collab_state
        return payload
    else:
        raise ValueError(f"unsupported action: {action}")

    payload = _ticket_to_dict(ticket)
    payload["approval_required"] = False
    if collab_state is not None:
        payload["collab_graph"] = collab_state
    return payload


def _execute_action_without_approval(
    runtime: OpsApiRuntime, *, ticket_id: str, action: str, payload: dict[str, Any]
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
        _execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action="resolve",
            actor_id=actor_id,
            payload=payload,
        )
        return runtime.ticket_api.require_ticket(ticket_id)
    if action in {"customer-confirm", "operator-close"}:
        _execute_v2_ticket_action(
            runtime,
            ticket_id=ticket_id,
            action=action,
            actor_id=actor_id,
            payload=payload,
        )
        return runtime.ticket_api.require_ticket(ticket_id)
    if action == "close":
        _execute_close_compat_action(
            runtime,
            ticket_id=ticket_id,
            actor_id=actor_id,
            payload=payload,
        )
        return runtime.ticket_api.require_ticket(ticket_id)
    raise ValueError(f"unsupported action: {action}")


def _execute_v2_ticket_action(
    runtime: OpsApiRuntime,
    *,
    ticket_id: str,
    action: str,
    actor_id: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    session_id = str(
        payload.get("session_id") or runtime.ticket_api.require_ticket(ticket_id).session_id
    ).strip()
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
        close_reason = str(
            payload.get("close_reason") or payload.get("reason") or "operator_forced_close"
        )
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


def _execute_close_compat_action(
    runtime: OpsApiRuntime,
    *,
    ticket_id: str,
    actor_id: str,
    payload: dict[str, Any],
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
    trace_id = str(payload.get("trace_id") or _ticket_trace_id(ticket) or new_trace_id()).strip()
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
            reason=str(
                payload.get("close_reason") or payload.get("reason") or "operator_forced_close"
            ),
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


def _run_session_new_issue(
    runtime: OpsApiRuntime,
    *,
    session_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if runtime.gateway.bindings.session_mapper.get(session_id) is None:
        raise KeyError(f"session {session_id} not found")
    actor_id = str(payload.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")
    reason = str(payload.get("reason") or "new_issue_requested").strip() or "new_issue_requested"
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()
    runtime.gateway.bindings.session_mapper.begin_new_issue(
        session_id,
        metadata={
            "session_mode": "awaiting_new_issue",
            "last_intent": "new_issue_requested",
            "updated_by": actor_id,
            "new_issue_reason": reason,
        },
    )
    runtime.trace_logger.log(
        "session_new_issue",
        {
            "session_id": session_id,
            "actor_id": actor_id,
            "reason": reason,
            "event_type": "session_new_issue",
        },
        trace_id=trace_id,
        session_id=session_id,
    )
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "reason": reason,
        "event_type": "session_new_issue",
        "message": "Session switched to new issue mode.",
        "trace_id": trace_id,
        "session": _session_payload(runtime, session_id),
    }


def _run_session_end_v2(
    runtime: OpsApiRuntime,
    *,
    session_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if runtime.gateway.bindings.session_mapper.get(session_id) is None:
        raise KeyError(f"session {session_id} not found")
    actor_id = str(payload.get("actor_id") or "").strip()
    if not actor_id:
        raise ValueError("actor_id is required")
    reason = str(payload.get("reason") or "manual_end").strip() or "manual_end"
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()
    action_result = runtime.ticket_api_v2.end_session(
        session_id,
        actor_id=actor_id,
        reason=reason,
    )
    runtime.trace_logger.log(
        "session_end_v2",
        {
            "session_id": session_id,
            "actor_id": actor_id,
            "reason": reason,
            "event_type": action_result.event_type,
        },
        trace_id=trace_id,
        session_id=session_id,
    )
    return {
        **asdict(action_result),
        "trace_id": trace_id,
        "session": _session_payload(runtime, session_id),
    }


def _extract_runtime_trace_fields(
    result_payload: dict[str, Any],
    *,
    default_graph: str,
) -> tuple[str, str, list[str], dict[str, Any]]:
    trace_payload = result_payload.get("trace")
    trace_details = trace_payload if isinstance(trace_payload, dict) else {}
    runtime_graph = str(trace_details.get("graph") or default_graph)
    steps_payload = trace_details.get("steps")
    runtime_path: list[str] = []
    if isinstance(steps_payload, list):
        for item in steps_payload:
            if not isinstance(item, dict):
                continue
            step_name = str(item.get("step") or "").strip()
            if step_name:
                runtime_path.append(step_name)

    runtime_current_node = runtime_path[-1] if runtime_path else "unknown"
    decision_payload = result_payload.get("decision")
    decision = decision_payload if isinstance(decision_payload, dict) else {}
    runtime_state: dict[str, Any] = {
        "route": decision.get("route"),
        "high_risk_action_executed": bool(decision.get("high_risk_action_executed", False)),
    }
    session_action_payload = result_payload.get("session_action")
    if isinstance(session_action_payload, dict):
        session_action = str(session_action_payload.get("action") or "").strip()
        if session_action:
            runtime_state["session_action"] = session_action
    intake_result_payload = result_payload.get("intake_result")
    if isinstance(intake_result_payload, dict):
        runtime_state["intake_status"] = intake_result_payload.get("status")
    return runtime_graph, runtime_current_node, runtime_path, runtime_state


def _run_intake_graph_v2(
    runtime: OpsApiRuntime,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    metadata_payload = payload.get("metadata")
    metadata = dict(metadata_payload) if isinstance(metadata_payload, dict) else {}
    session_id = str(payload.get("session_id") or metadata.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    text = str(
        payload.get("text") or payload.get("message_text") or payload.get("query") or ""
    ).strip()
    if not text:
        raise ValueError("text is required")
    actor_id = (
        str(payload.get("actor_id") or metadata.get("actor_id") or "ops-api").strip() or "ops-api"
    )
    metadata.setdefault("actor_id", actor_id)
    if payload.get("ticket_id"):
        metadata.setdefault("ticket_id", str(payload.get("ticket_id")))

    previous_payload = payload.get("previous")
    previous = previous_payload if isinstance(previous_payload, dict) else None
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()
    session_control = detect_session_control(text)
    if session_control is not None and session_control.action in {"session_end", "new_issue"}:
        if session_control.action == "session_end":
            action_result = _run_session_end_v2(
                runtime,
                session_id=session_id,
                payload={
                    "actor_id": actor_id,
                    "reason": "user_requested_end",
                    "trace_id": trace_id,
                },
            )
        else:
            action_result = _run_session_new_issue(
                runtime,
                session_id=session_id,
                payload={
                    "actor_id": actor_id,
                    "reason": "user_requested_new_issue",
                    "trace_id": trace_id,
                },
            )
        control_result = {
            "session_id": session_id,
            "user_id": str(payload.get("user_id") or ""),
            "channel": str(payload.get("channel") or "ops-api"),
            "intent": "session_control",
            "decision": {
                "route": session_control.action,
                "high_risk_action_executed": False,
            },
            "intake_result": {
                "status": "skipped",
                "reason": f"session_control_{session_control.action}",
            },
            "investigation": None,
            "session_action": {
                "action": session_control.action,
                "reason": session_control.reason,
                "source": session_control.source,
                "priority": session_control.priority,
                "result": action_result,
            },
            "trace": {
                "graph": "intake_graph_v1",
                "previous_checkpoint": previous,
                "steps": [
                    {
                        "step": "input_received",
                        "details": {"session_id": session_id},
                        "at": datetime.now(UTC).isoformat(),
                    },
                    {
                        "step": "session_control_routed",
                        "details": {
                            "action": session_control.action,
                            "reason": session_control.reason,
                            "source": session_control.source,
                        },
                        "at": datetime.now(UTC).isoformat(),
                    },
                ],
            },
        }
        runtime.trace_logger.log(
            "intake_run_v2",
            {
                "session_id": session_id,
                "intent": control_result.get("intent"),
                "route": session_control.action,
                "advice_only": True,
                "high_risk_action_executed": False,
                "session_action": session_control.action,
                "session_action_reason": session_control.reason,
            },
            trace_id=trace_id,
            ticket_id=str(metadata.get("ticket_id") or "").strip() or None,
            session_id=session_id,
        )
        runtime_graph, runtime_current_node, runtime_path, runtime_state = _extract_runtime_trace_fields(
            control_result,
            default_graph="intake_graph_v1",
        )
        return {
            "result": control_result,
            "advice_only": True,
            "high_risk_action_executed": False,
            "runtime_graph": runtime_graph,
            "runtime_current_node": runtime_current_node,
            "runtime_path": runtime_path,
            "runtime_state": runtime_state,
            "trace": {
                "trace_id": trace_id,
                "graph": runtime_graph,
            },
        }

    result = runtime.intake_graph_runner(
        {
            "session_id": session_id,
            "user_id": str(payload.get("user_id") or ""),
            "text": text,
            "channel": str(payload.get("channel") or "ops-api"),
            "metadata": metadata,
        },
        previous=previous,
    )
    if not isinstance(result, dict):
        raise ValueError("intake graph returned invalid result")

    decision_payload = result.get("decision")
    decision = decision_payload if isinstance(decision_payload, dict) else {}
    investigation_payload = result.get("investigation")
    investigation = investigation_payload if isinstance(investigation_payload, dict) else {}
    safety_payload = investigation.get("safety")
    safety = safety_payload if isinstance(safety_payload, dict) else {}
    advice_only = bool(safety.get("advice_only", True))
    high_risk_action_executed = bool(decision.get("high_risk_action_executed", False))
    runtime.trace_logger.log(
        "intake_run_v2",
        {
            "session_id": session_id,
            "intent": result.get("intent"),
            "route": decision.get("route"),
            "advice_only": advice_only,
            "high_risk_action_executed": high_risk_action_executed,
        },
        trace_id=trace_id,
        ticket_id=str(metadata.get("ticket_id") or "").strip() or None,
        session_id=session_id,
    )
    runtime_graph, runtime_current_node, runtime_path, runtime_state = _extract_runtime_trace_fields(
        result,
        default_graph="intake_graph_v1",
    )
    return {
        "result": result,
        "advice_only": advice_only,
        "high_risk_action_executed": high_risk_action_executed,
        "runtime_graph": runtime_graph,
        "runtime_current_node": runtime_current_node,
        "runtime_path": runtime_path,
        "runtime_state": runtime_state,
        "trace": {
            "trace_id": trace_id,
            "graph": runtime_graph,
        },
    }


def _run_ticket_investigation_v2(
    runtime: OpsApiRuntime,
    *,
    ticket_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    actor_id = str(payload.get("actor_id") or "ops-api").strip() or "ops-api"
    question = str(
        payload.get("question")
        or payload.get("query")
        or ticket.latest_message
        or "Please investigate this ticket."
    ).strip()
    if not question:
        raise ValueError("question is required")
    trace_id = str(payload.get("trace_id") or _ticket_trace_id(ticket) or new_trace_id()).strip()
    investigation = run_ticket_investigation(
        runtime.investigation_agent,
        ticket_id=ticket_id,
        actor=actor_id,
        question=question,
    )
    safety_payload = investigation.get("safety")
    safety = safety_payload if isinstance(safety_payload, dict) else {}
    advice_only = bool(safety.get("advice_only", False))
    if not advice_only:
        safety = {
            **safety,
            "advice_only": True,
            "high_risk_actions_executed": [],
            "requires_hitl_for_terminal_actions": True,
        }
        investigation["safety"] = safety
        advice_only = True
    high_risk_actions_payload = safety.get("high_risk_actions_executed")
    high_risk_actions = (
        high_risk_actions_payload if isinstance(high_risk_actions_payload, list) else []
    )
    runtime.trace_logger.log(
        "ticket_investigation_v2",
        {
            "ticket_id": ticket_id,
            "actor_id": actor_id,
            "question": question,
            "advice_only": advice_only,
            "high_risk_actions_executed": list(high_risk_actions),
        },
        trace_id=trace_id,
        ticket_id=ticket_id,
        session_id=ticket.session_id,
    )
    trace_payload = investigation.get("trace")
    trace_details = trace_payload if isinstance(trace_payload, dict) else {}
    return {
        "ticket_id": ticket_id,
        "session_id": ticket.session_id,
        "question": question,
        "investigation": investigation,
        "advice_only": advice_only,
        "trace": {
            "trace_id": trace_id,
            "agent": str(trace_details.get("agent") or "ticket_investigation_agent_v1"),
        },
    }


def _build_ticket_assist_payload(runtime: OpsApiRuntime, ticket_id: str) -> dict[str, Any]:
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
    llm_trace = _extract_llm_trace_for_ticket(runtime, ticket)
    if latest_summary_trace:
        llm_trace = {**llm_trace, **_normalize_llm_trace(latest_summary_trace)}
    if llm_trace.get("degraded"):
        risk_flags = sorted({*risk_flags, "llm_degraded"})
    ticket_grounding_sources = _extract_grounding_sources(ticket, runtime.retriever)
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


def _pending_action_to_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "as_dict"):
        return dict(item.as_dict())
    if isinstance(item, dict):
        return dict(item)
    return {}


def handle_api_request(
    runtime: OpsApiRuntime,
    *,
    method: str,
    path: str,
    query: dict[str, str],
    body: dict[str, Any] | None,
    request_id: str | None = None,
) -> ApiResponse:
    req_id = _request_id(request_id)
    payload = body or {}

    try:
        if method == "GET" and path == "/healthz":
            return _json_response(req_id, {"status": "ok"})

        if method == "GET" and path == "/api/dashboard/summary":
            return _json_response(req_id, {"data": _dashboard_summary(runtime)})
        if method == "GET" and path == "/api/dashboard/recent-errors":
            return _json_response(req_id, {"data": _dashboard_recent_errors(runtime)})

        if method == "GET" and path == "/api/tickets":
            page = _parse_int(query.get("page"), default=1, minimum=1, maximum=100000)
            page_size = _parse_int(query.get("page_size"), default=20, minimum=1, maximum=200)
            filtered_tickets = _filter_tickets(runtime, query)
            total = len(filtered_tickets)
            start = (page - 1) * page_size
            end = start + page_size
            return _json_response(
                req_id,
                {
                    "items": [_ticket_to_dict(item) for item in filtered_tickets[start:end]],
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                },
            )

        if session_read_response := try_handle_session_read_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            json_response=_json_response,
            error_response=_error,
            session_payload=_session_payload,
            session_ticket_list=_session_ticket_list,
            session_reply_events=_session_reply_events,
        ):
            return session_read_response

        if ticket_read_response := try_handle_ticket_read_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            json_response=_json_response,
            error_response=_error,
            ticket_to_dict=_ticket_to_dict,
            ticket_timeline_events=_ticket_timeline_events,
            ticket_reply_events=_ticket_reply_events,
            ticket_duplicate_candidates=_ticket_duplicate_candidates,
            pending_action_to_dict=_pending_action_to_dict,
            build_ticket_assist_payload=_build_ticket_assist_payload,
            extract_similar_cases=_extract_similar_cases,
            extract_grounding_sources=_extract_grounding_sources,
        ):
            return ticket_read_response

        if copilot_response := try_handle_copilot_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            payload=payload,
            json_response=_json_response,
            error_response=_error,
            copilot_disambiguate_payload=_copilot_disambiguate_payload,
            require_copilot_query=_require_copilot_query,
            build_copilot_operator_payload=lambda rt, query_text: _build_copilot_operator_payload(
                rt, query_text=query_text
            ),
            build_copilot_queue_payload=_build_copilot_queue_payload,
            build_copilot_ticket_payload=lambda rt, ticket, query_text: (
                _build_copilot_ticket_payload(rt, ticket, query_text=query_text)
            ),
            build_copilot_dispatch_payload=lambda rt, query_text: _build_copilot_dispatch_payload(
                rt, query_text=query_text
            ),
        ):
            return copilot_response

        if retrieval_or_approval_response := try_handle_retrieval_and_approval_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            payload=payload,
            query=query,
            json_response=_json_response,
            error_response=_error,
            parse_int=_parse_int,
            search_kb_tool=search_kb,
            retrieval_health_payload=_retrieval_health_payload,
            pending_action_to_dict=_pending_action_to_dict,
            paginate_payload=_paginate,
        ):
            return retrieval_or_approval_response

        if session_control_response := try_handle_session_control_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            payload=payload,
            json_response=_json_response,
            error_response=_error,
            session_payload=_session_payload,
            run_session_new_issue=_run_session_new_issue,
            trace_id_factory=new_trace_id,
        ):
            return session_control_response

        if ticket_action_response := try_handle_ticket_action_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            payload=payload,
            json_response=_json_response,
            error_response=_error,
            ticket_to_dict=_ticket_to_dict,
            session_payload=_session_payload,
            merge_suggestion_decision=_merge_suggestion_decision,
            resolve_action=_resolve_action,
            run_ticket_investigation_v2=_run_ticket_investigation_v2,
            run_intake_graph_v2=_run_intake_graph_v2,
            run_session_end_v2=_run_session_end_v2,
        ):
            return ticket_action_response

        if approval_action_response := try_handle_approval_action_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            payload=payload,
            json_response=_json_response,
            error_response=_error,
            ticket_to_dict=_ticket_to_dict,
            execute_action_without_approval=_execute_action_without_approval,
        ):
            return approval_action_response

        if method == "GET" and path == "/api/queues":
            return _json_response(req_id, {"items": _queue_summary(runtime)})
        if method == "GET" and path == "/api/queues/summary":
            return _json_response(req_id, {"items": _queue_summary(runtime)})

        if trace_response := try_handle_trace_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            query=query,
            json_response=_json_response,
            error_response=_error,
            parse_int=_parse_int,
            trace_groups=_trace_groups,
            trace_summary=_trace_summary,
            parse_iso_datetime=_parse_iso_datetime,
            trace_detail_event_to_dict=_trace_detail_event_to_dict,
        ):
            return trace_response

        if kb_response := try_handle_kb_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            query=query,
            payload=payload,
            json_response=_json_response,
            error_response=_error,
            parse_int=_parse_int,
            load_kb_docs=_load_kb_docs,
            write_kb_docs=_write_kb_docs,
        ):
            return kb_response

        if channel_response := try_handle_channel_routes(
            runtime=runtime,
            method=method,
            path=path,
            req_id=req_id,
            query=query,
            json_response=_json_response,
            reliability_snapshot=_reliability_snapshot,
            paginate_payload=_paginate,
            collect_openclaw_status=lambda rt: collect_status(rt.app_config.environment),
        ):
            return channel_response

        if method == "GET" and path == "/api/agents/assignees":
            tickets = runtime.repository.list_tickets(limit=3000, offset=0)
            assignees = sorted({ticket.assignee for ticket in tickets if ticket.assignee})
            if not assignees:
                assignees = ["u_ops_01", "u_ops_02", "u_supervisor_01"]
            return _json_response(req_id, {"items": assignees})

        return _error(
            req_id,
            code="not_found",
            message=f"route not found: {method} {path}",
            status=HTTPStatus.NOT_FOUND,
        )
    except KeyError as exc:
        return _error(req_id, code="not_found", message=str(exc), status=HTTPStatus.NOT_FOUND)
    except ValueError as exc:
        return _error(
            req_id, code="invalid_payload", message=str(exc), status=HTTPStatus.BAD_REQUEST
        )
    except Exception as exc:
        return _error(
            req_id,
            code="internal_error",
            message=DEFAULT_ERROR_MESSAGE,
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            details={"error": str(exc)},
        )


def _build_handler(runtime: OpsApiRuntime) -> type[BaseHTTPRequestHandler]:
    return build_http_handler(
        runtime=runtime,
        dispatch_request=handle_api_request,
        request_id_factory=_request_id,
        error_factory=_error,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run support-agent Ops API server")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="HTTP bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP bind port")
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
            argv=[sys.executable, "-m", "scripts.ops_api_server", *sys.argv[1:]],
            watch_roots=build_default_watch_roots(repo_root),
            interval_seconds=args.reload_interval,
            service_name="ops_api_server",
        )
    runtime = build_runtime(args.env)
    handler = _build_handler(runtime)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "status": "starting",
                "host": args.host,
                "port": args.port,
                "healthz": "/healthz",
                "api_base": "/api/*",
                "contract": "api-contract-v2 (compat-v1 enabled)",
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
