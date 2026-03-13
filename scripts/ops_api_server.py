from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.agents.deep.ticket_investigation_agent import (
    TicketInvestigationAgent,
    build_ticket_investigation_agent,
    run_ticket_investigation,
)
from app.application.intake_service import IntakeService
from app.application.session_service import SessionContextStoreProtocol, SessionService
from app.domain.conversation.conversation_state import ConversationState
from app.domain.ticket.ticket_api import TicketAPI as TicketAPIV2
from app.domain.ticket.ticket_workflow_state import TicketWorkflowState
from app.graph_runtime.intake_graph import build_intake_graph
from config import AppConfig, load_app_config
from core.disambiguation import NewIssueDetector, detect_session_control
from core.hitl.approval_policy import ApprovalPolicy
from core.hitl.approval_runtime import ApprovalRuntime
from core.hitl.handoff_context import build_approval_context
from core.intent_router import IntentDecision, IntentRouter
from core.recommended_actions_engine import RecommendedActionsEngine
from core.retrieval.source_attribution import build_source_payloads
from core.retriever import Retriever
from core.summary_engine import SummaryEngine
from core.ticket_api import TicketAPI as LegacyTicketAPI
from core.trace_logger import JsonTraceLogger, new_trace_id
from llm import build_summary_model_adapter
from openclaw_adapter.bindings import build_default_bindings
from openclaw_adapter.gateway import OpenClawGateway
from openclaw_adapter.session_mapper import SessionMapper
from scripts.gateway_status import collect_status, summarize_reliability
from storage.models import KBDocument, Ticket
from storage.ticket_repository import TicketRepository
from tools.search_kb import search_kb

DEFAULT_HOST = os.getenv("OPS_API_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("OPS_API_PORT", "18082"))
DEFAULT_ERROR_MESSAGE = "请求处理失败，请稍后重试。"

TICKET_DETAIL_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)$")
TICKET_EVENTS_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/events$")
TICKET_REPLY_EVENTS_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/reply-events$")
TICKET_DUPLICATES_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/duplicates$")
TICKET_ASSIST_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/assist$")
TICKET_SIMILAR_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/similar-cases$")
TICKET_GROUNDING_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/grounding-sources$")
TICKET_PENDING_ACTIONS_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/pending-actions$")
TICKET_MERGE_SUGGESTION_RE = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/merge-suggestion/(?P<decision>accept|reject)$"
)
TICKET_SWITCH_ACTIVE_RE = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/switch-active$")
TICKET_ACTION_RE = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/(claim|reassign|escalate|resolve|close)$"
)
TICKET_ACTION_V2_RE = re.compile(
    r"^/api/v2/tickets/(?P<ticket_id>[^/]+)/(resolve|customer-confirm|operator-close)$"
)
TICKET_INVESTIGATE_V2_RE = re.compile(r"^/api/v2/tickets/(?P<ticket_id>[^/]+)/investigate$")
APPROVAL_ACTION_RE = re.compile(r"^/api/approvals/(?P<approval_id>[^/]+)/(approve|reject)$")
COPILOT_TICKET_QUERY_RE = re.compile(r"^/api/copilot/ticket/(?P<ticket_id>[^/]+)/query$")
TRACE_DETAIL_RE = re.compile(r"^/api/traces/(?P<trace_id>[^/]+)$")
KB_DOC_RE = re.compile(r"^/api/kb/(?P<doc_id>[^/]+)$")
SESSION_DETAIL_RE = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)$")
SESSION_TICKETS_RE = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)/tickets$")
SESSION_REPLY_EVENTS_RE = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)/reply-events$")
SESSION_RESET_RE = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)/reset$")
SESSION_NEW_ISSUE_RE = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)/new-issue$")
SESSION_END_V2_RE = re.compile(r"^/api/v2/sessions/(?P<session_id>[^/]+)/end$")
COPILOT_DISAMBIGUATE_PATH = "/api/copilot/disambiguate"
INTAKE_GRAPH_RUN_V2_PATH = "/api/v2/intake/run"


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
    approval_runtime: ApprovalRuntime
    intake_graph_runner: Any
    investigation_agent: TicketInvestigationAgent
    kb_store_path: Path


@dataclass(frozen=True)
class ApiResponse:
    status: HTTPStatus
    payload: dict[str, Any]


class _SessionMapperConversationStore(SessionContextStoreProtocol):
    """Persist ConversationState onto SessionMapper metadata."""

    def __init__(self, session_mapper: SessionMapper) -> None:
        self._session_mapper = session_mapper

    def get(self, session_id: str) -> ConversationState | None:
        binding = self._session_mapper.get(session_id)
        if binding is None:
            return None

        context = self._session_mapper.get_session_context(session_id)
        mode = _conversation_mode_from_session_context(str(context.get("session_mode") or ""))
        return ConversationState(
            session_id=session_id,
            active_ticket_id=str(context.get("active_ticket_id") or "").strip() or None,
            recent_ticket_ids=[
                str(item).strip()
                for item in context.get("recent_ticket_ids", [])
                if str(item).strip()
            ],
            conversation_mode=mode,
            awaiting_customer_confirmation=bool(
                binding.metadata.get("awaiting_customer_confirmation", False)
            ),
            last_user_intent=str(context.get("last_intent") or "").strip() or None,
        )

    def save(self, state: ConversationState) -> None:
        metadata = {
            "awaiting_customer_confirmation": state.awaiting_customer_confirmation,
            "last_intent": state.last_user_intent,
            "session_context": {
                "active_ticket_id": state.active_ticket_id,
                "recent_ticket_ids": [
                    str(item).strip() for item in state.recent_ticket_ids if str(item).strip()
                ][:5],
                "session_mode": _session_mode_from_conversation_mode(state.conversation_mode),
                "last_intent": state.last_user_intent,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        }

        if state.active_ticket_id:
            self._session_mapper.set_ticket_id(
                state.session_id,
                state.active_ticket_id,
                metadata=metadata,
            )
            return

        self._session_mapper.reset_session_context(
            state.session_id,
            metadata=metadata,
            keep_recent=False,
        )
        self._session_mapper.get_or_create(state.session_id, metadata=metadata)


class _TicketWorkflowRepositoryAdapter:
    """Bridge storage repository to app.domain.ticket.TicketAPI protocol."""

    def __init__(self, repository: TicketRepository) -> None:
        self._repository = repository

    def get_workflow_state(self, ticket_id: str) -> TicketWorkflowState:
        ticket = self._repository.get_ticket(ticket_id)
        if ticket is None:
            raise KeyError(f"Ticket not found: {ticket_id}")
        approval_state = "pending_approval" if ticket.handoff_state == "pending_approval" else "none"
        return TicketWorkflowState(
            ticket_id=ticket.ticket_id,
            status=ticket.status,
            handoff_state=ticket.handoff_state,
            lifecycle_stage=ticket.lifecycle_stage,
            approval_state=approval_state,
        )

    def update_ticket_fields(self, ticket_id: str, fields: dict[str, Any]) -> None:
        self._repository.update_ticket(ticket_id, dict(fields))

    def append_event(self, ticket_id: str, event_type: str, payload: dict[str, Any]) -> None:
        actor_id = str(payload.get("actor_id") or "app-ticket-api")
        actor_type = str(payload.get("actor_type") or "agent")
        self._repository.append_event(
            ticket_id=ticket_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )


def _conversation_mode_from_session_context(raw_mode: str) -> str:
    mode = raw_mode.strip().lower()
    if mode in {"faq"}:
        return "faq"
    if mode in {"single_issue", "multi_issue", "support"}:
        return "support"
    return "idle"


def _session_mode_from_conversation_mode(mode: str) -> str:
    if mode == "faq":
        return "single_issue"
    if mode == "support":
        return "multi_issue"
    return "awaiting_new_issue"


def _seed_root() -> Path:
    return Path(__file__).resolve().parents[1] / "seed_data"


def _default_kb_store_path(app_config: AppConfig) -> Path:
    return Path(app_config.storage.sqlite_path).with_name("ops_api_kb.json")


def build_runtime(environment: str | None) -> OpsApiRuntime:
    app_config = load_app_config(environment)
    bindings = build_default_bindings(app_config)
    gateway = OpenClawGateway(bindings)

    sqlite_path = Path(app_config.storage.sqlite_path)
    repository = TicketRepository(sqlite_path)
    repository.apply_migrations()

    ticket_api = LegacyTicketAPI(repository, session_mapper=bindings.session_mapper)
    ticket_repo_v2 = _TicketWorkflowRepositoryAdapter(repository)
    session_store_v2 = _SessionMapperConversationStore(bindings.session_mapper)
    session_service_v2 = SessionService(session_store_v2)
    ticket_api_v2 = TicketAPIV2(ticket_repo=ticket_repo_v2, session_service=session_service_v2)
    retriever = Retriever(_seed_root())
    summary_engine = SummaryEngine(model_adapter=build_summary_model_adapter(app_config.llm))
    recommendation_engine = RecommendedActionsEngine()
    approval_runtime = ApprovalRuntime(
        ticket_api=ticket_api,
        policy=ApprovalPolicy.default(),
        trace_logger=bindings.trace_logger,
    )

    kb_store_path = _default_kb_store_path(app_config)
    if not kb_store_path.exists():
        _write_kb_docs(kb_store_path, _seed_kb_docs())

    investigation_agent = build_ticket_investigation_agent(
        read_ticket_tool=lambda ticket_id: _ticket_to_dict(ticket_api.require_ticket(str(ticket_id))),
        read_ticket_events_tool=lambda ticket_id: [
            _event_to_dict(item) for item in ticket_api.list_events(str(ticket_id))
        ],
        search_kb_tool=lambda query: search_kb(
            retriever=retriever,
            source_type="grounded",
            query=str(query),
            top_k=3,
            retrieval_mode=None,
        ),
        search_similar_cases_tool=lambda ticket_id: _extract_similar_cases(
            ticket_api.require_ticket(str(ticket_id)),
            retriever,
        ),
        get_grounding_sources_tool=lambda ticket_id: _extract_grounding_sources(
            ticket_api.require_ticket(str(ticket_id)),
            retriever,
        ),
    )
    intake_graph_runner = build_intake_graph(IntakeService(), investigation_agent)

    return OpsApiRuntime(
        app_config=app_config,
        gateway=gateway,
        ticket_api=ticket_api,
        ticket_api_v2=ticket_api_v2,
        repository=repository,
        trace_logger=bindings.trace_logger,
        retriever=retriever,
        summary_engine=summary_engine,
        recommendation_engine=recommendation_engine,
        approval_runtime=approval_runtime,
        intake_graph_runner=intake_graph_runner,
        investigation_agent=investigation_agent,
        kb_store_path=kb_store_path,
    )


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
            str(item.get("ticket_id") or "")
            for item in items
            if item.get("ticket_id")
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
    summary = _dashboard_summary(runtime)
    grounding_sources = _copilot_grounding_sources(runtime, query_text, top_k=5)
    sla_risk = int(summary["sla_warning_count"]) + int(summary["sla_breached_count"])
    answer = (
        f"Operator建议：当前处理中{summary['in_progress_count']}单，"
        f"SLA风险{sla_risk}单，升级单{summary['escalated_count']}。"
        "优先处理升级与SLA风险工单。"
    )
    risk_flags = ["low_grounding"] if not grounding_sources else []
    return {
        "scope": "operator",
        "query": query_text,
        "answer": answer,
        "dashboard_summary": summary,
        "grounding_sources": grounding_sources,
        "risk_flags": risk_flags,
        "llm_trace": _default_copilot_llm_trace("operator"),
        "generated_at": datetime.now(UTC).isoformat(),
    }


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
        f"Queue建议：优先关注队列 {focus_queue}。"
        if focus
        else "Queue建议：当前无可分析队列数据。"
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
    rows = _queue_summary(runtime)
    priorities = sorted(
        rows,
        key=lambda item: (
            int(item.get("escalated_count", 0)),
            int(item.get("breached_count", 0)),
            int(item.get("in_progress_count", 0)),
        ),
        reverse=True,
    )
    top_queue = str(priorities[0]["queue_name"]) if priorities else "n/a"
    answer = (
        f"Dispatch建议：优先向队列 {top_queue} 投放处理资源，"
        "并优先分配升级与超时风险工单。"
        if priorities
        else "Dispatch建议：暂无可调度的队列负载数据。"
    )
    grounding_sources = _copilot_grounding_sources(runtime, query_text, top_k=5)
    risk_flags = ["low_grounding"] if not grounding_sources else []
    return {
        "scope": "dispatch",
        "query": query_text,
        "answer": answer,
        "dispatch_priority": priorities[:5],
        "grounding_sources": grounding_sources,
        "risk_flags": risk_flags,
        "llm_trace": _default_copilot_llm_trace("dispatch"),
        "generated_at": datetime.now(UTC).isoformat(),
    }


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
            }
        )
        return ticket_payload

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
        return payload
    else:
        raise ValueError(f"unsupported action: {action}")

    payload = _ticket_to_dict(ticket)
    payload["approval_required"] = False
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


def _execute_close_compat_action(
    runtime: OpsApiRuntime,
    *,
    ticket_id: str,
    actor_id: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    requested_action = str(payload.get("action") or "").strip().replace("-", "_").lower() or None
    close_reason = str(payload.get("close_reason") or "").strip().lower()
    resolved_action = requested_action or _resolve_close_action_by_reason(close_reason)
    session_id = str(payload.get("session_id") or ticket.session_id).strip() or None
    trace_id = str(payload.get("trace_id") or _ticket_trace_id(ticket) or new_trace_id()).strip()
    if resolved_action not in {"customer_confirm", "operator_close"}:
        raise ValueError(
            "ambiguous close action; provide action=customer_confirm|operator_close or deterministic close_reason"
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
    if normalized == "customer_confirmed":
        return "customer_confirm"
    if normalized in {"operator_forced_close", "agent_close", "manual_close"}:
        return "operator_close"
    return None


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
    text = str(payload.get("text") or payload.get("message_text") or payload.get("query") or "").strip()
    if not text:
        raise ValueError("text is required")
    actor_id = str(payload.get("actor_id") or metadata.get("actor_id") or "ops-api").strip() or "ops-api"
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
                "route": control_result["decision"]["route"],
                "advice_only": True,
                "high_risk_action_executed": False,
                "session_action": session_control.action,
                "session_action_reason": session_control.reason,
            },
            trace_id=trace_id,
            ticket_id=str(metadata.get("ticket_id") or "").strip() or None,
            session_id=session_id,
        )
        return {
            "result": control_result,
            "advice_only": True,
            "high_risk_action_executed": False,
            "trace": {
                "trace_id": trace_id,
                "graph": "intake_graph_v1",
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
    trace_payload = result.get("trace")
    trace_details = trace_payload if isinstance(trace_payload, dict) else {}
    return {
        "result": result,
        "advice_only": advice_only,
        "high_risk_action_executed": high_risk_action_executed,
        "trace": {
            "trace_id": trace_id,
            "graph": str(trace_details.get("graph") or "intake_graph_v1"),
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
    high_risk_actions = high_risk_actions_payload if isinstance(high_risk_actions_payload, list) else []
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

        if method == "GET" and (match := SESSION_DETAIL_RE.match(path)):
            session_id = match.group("session_id")
            data = _session_payload(runtime, session_id)
            if data is None:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"data": data})

        if method == "GET" and (match := SESSION_TICKETS_RE.match(path)):
            session_id = match.group("session_id")
            data = _session_payload(runtime, session_id)
            if data is None:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"items": _session_ticket_list(runtime, session_id)})

        if method == "GET" and (match := SESSION_REPLY_EVENTS_RE.match(path)):
            session_id = match.group("session_id")
            data = _session_payload(runtime, session_id)
            if data is None:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"items": _session_reply_events(runtime, session_id)})

        if method == "GET" and (match := TICKET_DETAIL_RE.match(path)):
            ticket_id = match.group("ticket_id")
            ticket = runtime.ticket_api.get_ticket(ticket_id)
            if ticket is None:
                return _error(
                    req_id,
                    code="ticket_not_found",
                    message=f"ticket {ticket_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"data": _ticket_to_dict(ticket)})

        if method == "GET" and (match := TICKET_EVENTS_RE.match(path)):
            ticket_id = match.group("ticket_id")
            return _json_response(req_id, {"items": _ticket_timeline_events(runtime, ticket_id)})

        if method == "GET" and (match := TICKET_REPLY_EVENTS_RE.match(path)):
            ticket_id = match.group("ticket_id")
            ticket = runtime.ticket_api.get_ticket(ticket_id)
            if ticket is None:
                return _error(
                    req_id,
                    code="ticket_not_found",
                    message=f"ticket {ticket_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"items": _ticket_reply_events(runtime, ticket_id)})

        if method == "GET" and (match := TICKET_DUPLICATES_RE.match(path)):
            ticket_id = match.group("ticket_id")
            ticket = runtime.ticket_api.get_ticket(ticket_id)
            if ticket is None:
                return _error(
                    req_id,
                    code="ticket_not_found",
                    message=f"ticket {ticket_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(
                req_id,
                {"items": _ticket_duplicate_candidates(runtime, ticket_id)},
            )

        if method == "GET" and (match := TICKET_PENDING_ACTIONS_RE.match(path)):
            ticket_id = match.group("ticket_id")
            actions = runtime.approval_runtime.list_ticket_actions(ticket_id)
            return _json_response(
                req_id,
                {
                    "items": [_pending_action_to_dict(item) for item in actions],
                },
            )

        if method == "GET" and (match := TICKET_ASSIST_RE.match(path)):
            ticket_id = match.group("ticket_id")
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
            return _json_response(
                req_id,
                {
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
                },
            )

        if method == "GET" and (match := TICKET_SIMILAR_RE.match(path)):
            ticket_id = match.group("ticket_id")
            ticket = runtime.ticket_api.require_ticket(ticket_id)
            return _json_response(
                req_id, {"items": _extract_similar_cases(ticket, runtime.retriever)}
            )

        if method == "GET" and (match := TICKET_GROUNDING_RE.match(path)):
            ticket_id = match.group("ticket_id")
            ticket = runtime.ticket_api.require_ticket(ticket_id)
            return _json_response(
                req_id,
                {"items": _extract_grounding_sources(ticket, runtime.retriever)},
            )

        if method == "POST" and path == COPILOT_DISAMBIGUATE_PATH:
            session_id = str(payload.get("session_id") or "").strip()
            message_text = str(payload.get("message_text") or payload.get("query") or "").strip()
            actor_id = str(payload.get("actor_id") or "ops-api").strip() or "ops-api"
            trace_id = str(payload.get("trace_id") or "").strip() or None
            if not session_id:
                return _error(
                    req_id,
                    code="invalid_payload",
                    message="session_id is required",
                    status=HTTPStatus.BAD_REQUEST,
                )
            if not message_text:
                return _error(
                    req_id,
                    code="invalid_payload",
                    message="message_text is required",
                    status=HTTPStatus.BAD_REQUEST,
                )
            if runtime.gateway.bindings.session_mapper.get(session_id) is None:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            try:
                data = _copilot_disambiguate_payload(
                    runtime,
                    session_id=session_id,
                    message_text=message_text,
                    actor_id=actor_id,
                    trace_id=trace_id,
                )
            except KeyError:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"data": data})

        if method == "POST" and path == "/api/copilot/operator/query":
            query_text, error = _require_copilot_query(req_id, payload)
            if error is not None:
                return error
            return _json_response(
                req_id,
                {"data": _build_copilot_operator_payload(runtime, query_text=query_text or "")},
            )

        if method == "POST" and path == "/api/copilot/queue/query":
            query_text, error = _require_copilot_query(req_id, payload)
            if error is not None:
                return error
            queue_name = str(payload.get("queue") or "").strip() or None
            return _json_response(
                req_id,
                {
                    "data": _build_copilot_queue_payload(
                        runtime,
                        query_text=query_text or "",
                        queue_name=queue_name,
                    )
                },
            )

        if method == "POST" and (match := COPILOT_TICKET_QUERY_RE.match(path)):
            query_text, error = _require_copilot_query(req_id, payload)
            if error is not None:
                return error
            ticket_id = match.group("ticket_id")
            ticket = runtime.ticket_api.require_ticket(ticket_id)
            return _json_response(
                req_id,
                {
                    "data": _build_copilot_ticket_payload(
                        runtime, ticket, query_text=query_text or ""
                    )
                },
            )

        if method == "POST" and path == "/api/copilot/dispatch/query":
            query_text, error = _require_copilot_query(req_id, payload)
            if error is not None:
                return error
            return _json_response(
                req_id,
                {"data": _build_copilot_dispatch_payload(runtime, query_text=query_text or "")},
            )

        if method == "POST" and path == "/api/retrieval/search":
            query_text = str(payload.get("query") or "").strip()
            if not query_text:
                return _error(
                    req_id,
                    code="invalid_payload",
                    message="query is required",
                )
            source_type = str(payload.get("source_type") or "grounded").strip().lower()
            top_k = _parse_int(str(payload.get("top_k") or "5"), default=5, minimum=1, maximum=20)
            retrieval_mode = str(payload.get("retrieval_mode") or "").strip() or None
            try:
                items = search_kb(
                    retriever=runtime.retriever,
                    source_type=source_type,
                    query=query_text,
                    top_k=top_k,
                    retrieval_mode=retrieval_mode,
                )
            except ValueError as exc:
                return _error(req_id, code="invalid_payload", message=str(exc))
            return _json_response(
                req_id,
                {
                    "items": items,
                    "query": query_text,
                    "source_type": source_type,
                    "retrieval_mode": retrieval_mode
                    or ("hybrid" if source_type in {"grounded", "hybrid"} else "lexical"),
                },
            )

        if method == "GET" and path == "/api/retrieval/health":
            return _json_response(req_id, {"data": _retrieval_health_payload(runtime)})

        if method == "GET" and path == "/api/approvals/pending":
            pending_items = [
                _pending_action_to_dict(item)
                for item in runtime.approval_runtime.list_pending_actions()
            ]
            return _json_response(req_id, _paginate(pending_items, query=query))

        if method == "POST" and (match := SESSION_RESET_RE.match(path)):
            session_id = match.group("session_id")
            if runtime.gateway.bindings.session_mapper.get(session_id) is None:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            actor_id = str(payload.get("actor_id") or "ops-api").strip()
            runtime.gateway.bindings.session_mapper.reset_session_context(
                session_id,
                metadata={
                    "session_mode": "awaiting_new_issue",
                    "last_intent": "session_reset",
                    "updated_by": actor_id,
                },
                keep_recent=True,
            )
            data = _session_payload(runtime, session_id)
            if data is None:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"data": data})

        if method == "POST" and (match := SESSION_NEW_ISSUE_RE.match(path)):
            session_id = match.group("session_id")
            try:
                action_result = _run_session_new_issue(
                    runtime,
                    session_id=session_id,
                    payload={
                        "actor_id": str(payload.get("actor_id") or "ops-api").strip() or "ops-api",
                        "reason": str(payload.get("reason") or "new_issue_requested").strip()
                        or "new_issue_requested",
                        "trace_id": str(payload.get("trace_id") or new_trace_id()).strip(),
                    },
                )
            except KeyError:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            data = action_result.get("session")
            if not isinstance(data, dict):
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(req_id, {"data": data})

        if method == "POST" and (match := TICKET_SWITCH_ACTIVE_RE.match(path)):
            ticket_id = match.group("ticket_id")
            ticket = runtime.ticket_api.require_ticket(ticket_id)
            session_id = str(payload.get("session_id") or ticket.session_id).strip()
            if not session_id:
                return _error(
                    req_id,
                    code="invalid_payload",
                    message="session_id is required",
                    status=HTTPStatus.BAD_REQUEST,
                )
            if session_id != ticket.session_id:
                return _error(
                    req_id,
                    code="invalid_payload",
                    message="ticket does not belong to target session",
                    status=HTTPStatus.BAD_REQUEST,
                )
            actor_id = str(payload.get("actor_id") or "ops-api").strip()
            runtime.ticket_api.switch_active_session_ticket(
                session_id,
                ticket_id,
                metadata={
                    "updated_by": actor_id,
                    "session_mode": "multi_issue",
                },
            )
            session_data = _session_payload(runtime, session_id)
            if session_data is None:
                return _error(
                    req_id,
                    code="session_not_found",
                    message=f"session {session_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            return _json_response(
                req_id,
                {
                    "data": {
                        "ticket": _ticket_to_dict(ticket),
                        "session": session_data,
                    }
                },
            )

        if method == "POST" and (match := TICKET_MERGE_SUGGESTION_RE.match(path)):
            ticket_id = match.group("ticket_id")
            decision = match.group("decision")
            result = _merge_suggestion_decision(
                runtime,
                ticket_id=ticket_id,
                decision=decision,
                payload=payload,
            )
            return _json_response(req_id, result)

        if method == "POST" and (match := TICKET_ACTION_V2_RE.match(path)):
            ticket_id = match.group("ticket_id")
            action = path.rsplit("/", 1)[-1]
            updated = _resolve_action(runtime, ticket_id=ticket_id, action=action, body=payload)
            return _json_response(req_id, {"data": updated})

        if method == "POST" and (match := TICKET_INVESTIGATE_V2_RE.match(path)):
            ticket_id = match.group("ticket_id")
            data = _run_ticket_investigation_v2(
                runtime,
                ticket_id=ticket_id,
                payload=payload,
            )
            return _json_response(req_id, {"data": data})

        if method == "POST" and path == INTAKE_GRAPH_RUN_V2_PATH:
            data = _run_intake_graph_v2(runtime, payload=payload)
            return _json_response(req_id, {"data": data})

        if method == "POST" and (match := SESSION_END_V2_RE.match(path)):
            session_id = match.group("session_id")
            data = _run_session_end_v2(runtime, session_id=session_id, payload=payload)
            return _json_response(req_id, {"data": data})

        if method == "POST" and (match := TICKET_ACTION_RE.match(path)):
            ticket_id = match.group("ticket_id")
            action = path.rsplit("/", 1)[-1]
            updated = _resolve_action(runtime, ticket_id=ticket_id, action=action, body=payload)
            return _json_response(req_id, {"data": updated})

        if method == "POST" and (match := APPROVAL_ACTION_RE.match(path)):
            approval_id = match.group("approval_id")
            decision = path.rsplit("/", 1)[-1]
            actor_id = str(payload.get("actor_id") or "").strip()
            if not actor_id:
                return _error(
                    req_id,
                    code="invalid_payload",
                    message="actor_id is required",
                    status=HTTPStatus.BAD_REQUEST,
                )
            note = str(payload.get("note") or "").strip() or None
            trace_id = str(payload.get("trace_id") or "").strip() or None

            if decision == "approve":
                ticket, pending_action = runtime.approval_runtime.get_pending_action(approval_id)
                action_payload = dict(pending_action.payload)
                action_payload.setdefault("actor_id", pending_action.requested_by)
                executed_ticket = _execute_action_without_approval(
                    runtime,
                    ticket_id=ticket.ticket_id,
                    action=pending_action.action_type,
                    payload=action_payload,
                )
                decided = runtime.approval_runtime.mark_approved(
                    approval_id,
                    actor_id=actor_id,
                    execution_ticket=executed_ticket,
                    note=note,
                    trace_id=trace_id,
                )
                return _json_response(
                    req_id,
                    {
                        "data": _ticket_to_dict(decided.ticket),
                        "approval": decided.pending_action.as_dict(),
                    },
                )

            if decision == "reject":
                decided = runtime.approval_runtime.mark_rejected(
                    approval_id,
                    actor_id=actor_id,
                    note=note,
                    trace_id=trace_id,
                )
                return _json_response(
                    req_id,
                    {
                        "data": _ticket_to_dict(decided.ticket),
                        "approval": decided.pending_action.as_dict(),
                    },
                )

            return _error(
                req_id,
                code="invalid_payload",
                message=f"unsupported approval decision: {decision}",
                status=HTTPStatus.BAD_REQUEST,
            )

        if method == "GET" and path == "/api/queues":
            return _json_response(req_id, {"items": _queue_summary(runtime)})
        if method == "GET" and path == "/api/queues/summary":
            return _json_response(req_id, {"items": _queue_summary(runtime)})

        if method == "GET" and path == "/api/traces":
            page = _parse_int(query.get("page"), default=1, minimum=1, maximum=100000)
            page_size = _parse_int(query.get("page_size"), default=20, minimum=1, maximum=200)
            summaries = [
                _trace_summary(runtime, trace_id, trace_events)
                for trace_id, trace_events in _trace_groups(runtime).items()
                if trace_events
            ]
            summaries.sort(
                key=lambda item: (
                    _parse_iso_datetime(str(item.get("created_at") or ""))
                    or datetime.min.replace(tzinfo=UTC),
                    str(item.get("trace_id") or ""),
                ),
                reverse=True,
            )
            filtered_traces: list[dict[str, Any]] = []
            for item in summaries:
                if query.get("trace_id") and item.get("trace_id") != query["trace_id"]:
                    continue
                if query.get("ticket_id") and (
                    str(item.get("ticket_id") or "") != query["ticket_id"]
                ):
                    continue
                if query.get("session_id") and (
                    str(item.get("session_id") or "") != query["session_id"]
                ):
                    continue
                if query.get("workflow") and item.get("workflow") != query["workflow"]:
                    continue
                if query.get("channel") and item.get("channel") != query["channel"]:
                    continue
                if query.get("provider") and item.get("provider") != query["provider"]:
                    continue
                if query.get("model") and str(item.get("model") or "") != query["model"]:
                    continue
                if query.get("prompt_version") and (
                    str(item.get("prompt_version") or "") != query["prompt_version"]
                ):
                    continue
                if (
                    query.get("error_only")
                    and str(item.get("error_only")).lower() != str(query["error_only"]).lower()
                ):
                    continue
                if (
                    query.get("handoff")
                    and str(item.get("handoff")).lower() != str(query["handoff"]).lower()
                ):
                    continue
                filtered_traces.append(item)
            total = len(filtered_traces)
            start = (page - 1) * page_size
            end = start + page_size
            return _json_response(
                req_id,
                {
                    "items": filtered_traces[start:end],
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                },
            )

        if method == "GET" and (match := TRACE_DETAIL_RE.match(path)):
            trace_id = match.group("trace_id")
            trace_events = runtime.trace_logger.query_by_trace(trace_id, limit=2000)
            if not trace_events:
                return _error(
                    req_id,
                    code="trace_not_found",
                    message=f"trace {trace_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            trace_summary = _trace_summary(runtime, trace_id, trace_events)
            retrieved_doc_ids: list[str] = []
            grounding_sources: list[dict[str, Any]] = []
            tool_calls: list[str] = []
            summary_text = ""
            for event in trace_events:
                event_type = str(event.get("event_type", ""))
                payload_dict = event.get("payload")
                payload = payload_dict if isinstance(payload_dict, dict) else {}
                if event_type == "ticket_context_retrieved":
                    retrieved_doc_ids = [
                        str(item) for item in payload.get("doc_ids", []) if isinstance(item, str)
                    ]
                    payload_sources = payload.get("grounding_sources")
                    if isinstance(payload_sources, list):
                        grounding_sources = [
                            dict(item) for item in payload_sources if isinstance(item, dict)
                        ]
                if event_type in {"tool_call_end", "tool_call"} and payload.get("tool"):
                    tool_calls.append(str(payload["tool"]))
                if event_type == "recommended_actions":
                    summary_text = json.dumps(payload.get("actions", []), ensure_ascii=False)
            return _json_response(
                req_id,
                {
                    "trace_id": trace_id,
                    "ticket_id": trace_summary.get("ticket_id"),
                    "session_id": trace_summary.get("session_id"),
                    "workflow": trace_summary.get("workflow"),
                    "channel": trace_summary.get("channel"),
                    "provider": trace_summary.get("provider"),
                    "model": trace_summary.get("model"),
                    "prompt_key": trace_summary.get("prompt_key"),
                    "prompt_version": trace_summary.get("prompt_version"),
                    "request_id": trace_summary.get("request_id"),
                    "token_usage": trace_summary.get("token_usage"),
                    "retry_count": trace_summary.get("retry_count"),
                    "success": trace_summary.get("success"),
                    "error": trace_summary.get("error"),
                    "fallback_used": trace_summary.get("fallback_used"),
                    "degraded": trace_summary.get("degraded"),
                    "degrade_reason": trace_summary.get("degrade_reason"),
                    "generation_type": trace_summary.get("generation_type"),
                    "route_decision": trace_summary.get("route_decision"),
                    "retrieved_docs": retrieved_doc_ids,
                    "grounding_sources": grounding_sources,
                    "tool_calls": tool_calls,
                    "summary": summary_text,
                    "handoff": trace_summary.get("handoff"),
                    "handoff_reason": trace_summary.get("handoff_reason"),
                    "error_only": trace_summary.get("error_only"),
                    "latency_ms": trace_summary.get("latency_ms"),
                    "created_at": trace_summary.get("created_at"),
                    "events": [
                        _trace_detail_event_to_dict(event, index=index)
                        for index, event in enumerate(trace_events)
                    ],
                },
            )

        if method == "GET" and path == "/api/kb":
            kb_docs = _load_kb_docs(runtime.kb_store_path)
            source_type = (query.get("source_type") or "").strip()
            q = (query.get("q") or "").strip().lower()
            page = _parse_int(query.get("page"), default=1, minimum=1, maximum=100000)
            page_size = _parse_int(query.get("page_size"), default=20, minimum=1, maximum=200)
            filtered_kb_docs: list[dict[str, Any]] = []
            for item in kb_docs:
                if source_type and str(item.get("source_type", "")) != source_type:
                    continue
                haystack = f"{item.get('title', '')} {item.get('content', '')}".lower()
                if q and q not in haystack:
                    continue
                filtered_kb_docs.append(item)
            total = len(filtered_kb_docs)
            start = (page - 1) * page_size
            end = start + page_size
            return _json_response(
                req_id,
                {
                    "items": filtered_kb_docs[start:end],
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                },
            )

        if method == "POST" and path == "/api/kb":
            doc_id = str(payload.get("doc_id") or f"doc_{uuid.uuid4().hex[:8]}")
            source_type = str(payload.get("source_type") or "").strip()
            title = str(payload.get("title") or "").strip()
            content = str(payload.get("content") or "").strip()
            tags = payload.get("tags") or []
            if source_type not in {"faq", "sop", "history_case"}:
                return _error(
                    req_id,
                    code="invalid_source_type",
                    message="source_type must be faq/sop/history_case",
                )
            if not title or not content:
                return _error(
                    req_id, code="invalid_payload", message="title and content are required"
                )

            kb_docs = _load_kb_docs(runtime.kb_store_path)
            if any(str(item.get("doc_id")) == doc_id for item in kb_docs):
                return _error(req_id, code="doc_exists", message=f"doc {doc_id} already exists")
            record = {
                "doc_id": doc_id,
                "source_type": source_type,
                "title": title,
                "content": content,
                "tags": [str(item) for item in tags if str(item).strip()],
                "updated_at": datetime.now(UTC).isoformat(),
            }
            kb_docs.append(record)
            _write_kb_docs(runtime.kb_store_path, kb_docs)
            return _json_response(req_id, {"data": record}, status=HTTPStatus.CREATED)

        if method == "PATCH" and (match := KB_DOC_RE.match(path)):
            doc_id = match.group("doc_id")
            kb_docs = _load_kb_docs(runtime.kb_store_path)
            updated_doc: dict[str, Any] | None = None
            for item in kb_docs:
                if str(item.get("doc_id")) != doc_id:
                    continue
                for key in ("title", "content", "source_type", "tags"):
                    if key in payload:
                        item[key] = payload[key]
                item["updated_at"] = datetime.now(UTC).isoformat()
                updated_doc = item
                break
            if updated_doc is None:
                return _error(
                    req_id,
                    code="doc_not_found",
                    message=f"doc {doc_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            _write_kb_docs(runtime.kb_store_path, kb_docs)
            return _json_response(req_id, {"data": updated_doc})

        if method == "DELETE" and (match := KB_DOC_RE.match(path)):
            doc_id = match.group("doc_id")
            kb_docs = _load_kb_docs(runtime.kb_store_path)
            remaining = [item for item in kb_docs if str(item.get("doc_id")) != doc_id]
            if len(remaining) == len(kb_docs):
                return _error(
                    req_id,
                    code="doc_not_found",
                    message=f"doc {doc_id} not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            _write_kb_docs(runtime.kb_store_path, remaining)
            return _json_response(req_id, {"deleted": True, "doc_id": doc_id})

        if method == "GET" and path == "/api/channels/health":
            recent = runtime.trace_logger.read_recent(limit=200)
            channels = runtime.gateway.bindings.channel_router.supported_channels
            reliability = _reliability_snapshot(runtime)
            signature_rows = reliability.get("signature", {}).get("items", [])
            replay_rows = reliability.get("replays", {}).get("items", [])
            retry_rows = reliability.get("retries", {}).get("items", [])
            signature_by_channel = {
                str(row.get("channel")): row
                for row in signature_rows
                if isinstance(row, dict) and row.get("channel")
            }
            rows = []
            for channel in channels:
                channel_events = [
                    event
                    for event in recent
                    if isinstance(event.get("payload"), dict)
                    and str((event["payload"]).get("channel", "")) == channel
                ]
                last_event = channel_events[-1] if channel_events else None
                last_error = None
                retry_state = "idle"
                if last_event and isinstance(last_event.get("payload"), dict):
                    payload_dict = last_event["payload"]
                    if "error" in payload_dict:
                        last_error = payload_dict.get("error")
                        retry_state = "retry_pending"

                channel_replays = [
                    row
                    for row in replay_rows
                    if isinstance(row, dict) and str(row.get("channel") or "") == channel
                ]
                replay_duplicates = sum(
                    1 for row in channel_replays if bool(row.get("accepted", True)) is False
                )
                channel_retry_failures = [
                    row
                    for row in retry_rows
                    if isinstance(row, dict)
                    and str(row.get("channel") or "") == channel
                    and str(row.get("event_type") or "") == "egress_failed"
                ]
                retry_observed = sum(
                    1
                    for row in channel_retry_failures
                    if isinstance(row.get("classification"), str)
                )
                retry_observability = (
                    round(retry_observed / len(channel_retry_failures), 4)
                    if channel_retry_failures
                    else 1.0
                )
                signature_row = signature_by_channel.get(channel, {})
                signature_checked = int(signature_row.get("checked", 0)) if signature_row else 0
                signature_rejected = int(signature_row.get("rejected", 0)) if signature_row else 0
                if signature_rejected > 0:
                    signature_state = "rejected"
                elif signature_checked > 0:
                    signature_state = "verified"
                else:
                    signature_state = "skipped"
                rows.append(
                    {
                        "channel": channel,
                        "connected": True,
                        "last_event_at": (last_event or {}).get("timestamp"),
                        "last_error": last_error,
                        "retry_state": retry_state,
                        "signature_state": signature_state,
                        "replay_duplicates": replay_duplicates,
                        "retry_observability": retry_observability,
                    }
                )
            return _json_response(
                req_id,
                {
                    "items": rows,
                    "summary": {
                        "signature": reliability.get("signature", {}).get("totals", {}),
                        "replays": {
                            "total": reliability.get("replays", {}).get("total", 0),
                            "duplicate_count": reliability.get("replays", {}).get(
                                "duplicate_count", 0
                            ),
                        },
                        "retries": {
                            "failed_count": reliability.get("retries", {}).get("failed_count", 0),
                            "observability_rate": reliability.get("retries", {}).get(
                                "observability_rate", 1.0
                            ),
                        },
                    },
                },
            )

        if method == "GET" and path == "/api/channels/events":
            recent_events = runtime.trace_logger.read_recent(limit=100)
            rows = []
            for event in recent_events:
                payload_dict = event.get("payload")
                payload = payload_dict if isinstance(payload_dict, dict) else {}
                channel_name = payload.get("channel")
                if not channel_name:
                    continue
                rows.append(
                    {
                        "timestamp": event.get("timestamp"),
                        "trace_id": event.get("trace_id"),
                        "channel": channel_name,
                        "event_type": event.get("event_type"),
                        "payload": payload,
                    }
                )
            return _json_response(req_id, {"items": rows[-50:]})

        if method == "GET" and path == "/api/openclaw/status":
            return _json_response(req_id, {"data": collect_status(runtime.app_config.environment)})

        if method == "GET" and path == "/api/openclaw/routes":
            channels = runtime.gateway.bindings.channel_router.supported_channels
            return _json_response(
                req_id,
                {
                    "gateway": runtime.app_config.gateway.name,
                    "routes": [
                        {"channel": channel, "mode": "ingress/session/routing"}
                        for channel in channels
                    ],
                },
            )

        if method == "GET" and path == "/api/openclaw/retries":
            reliability = _reliability_snapshot(runtime)
            retry_items = reliability.get("retries", {}).get("items", [])
            items = [row for row in retry_items if isinstance(row, dict)]
            return _json_response(
                req_id,
                {
                    **_paginate(items, query=query),
                    "observability_rate": reliability.get("retries", {}).get(
                        "observability_rate", 1.0
                    ),
                },
            )

        if method == "GET" and path == "/api/openclaw/replays":
            reliability = _reliability_snapshot(runtime)
            replay_items = reliability.get("replays", {}).get("items", [])
            items = [row for row in replay_items if isinstance(row, dict)]
            return _json_response(
                req_id,
                {
                    **_paginate(items, query=query),
                    "duplicate_count": reliability.get("replays", {}).get("duplicate_count", 0),
                    "duplicate_ratio": reliability.get("replays", {}).get("duplicate_ratio", 0.0),
                    "non_duplicate_ratio": reliability.get("replays", {}).get(
                        "non_duplicate_ratio", 1.0
                    ),
                },
            )

        if method == "GET" and path == "/api/openclaw/sessions":
            reliability = _reliability_snapshot(runtime)
            session_items = reliability.get("sessions", {}).get("items", [])
            items = [row for row in session_items if isinstance(row, dict)]
            return _json_response(
                req_id,
                {
                    **_paginate(items, query=query),
                    "bound_to_ticket": reliability.get("sessions", {}).get("bound_to_ticket", 0),
                },
            )

        if method == "GET" and path == "/api/channels/signature-status":
            reliability = _reliability_snapshot(runtime)
            signature_items = reliability.get("signature", {}).get("items", [])
            items = [row for row in signature_items if isinstance(row, dict)]
            return _json_response(
                req_id,
                {
                    **_paginate(items, query=query),
                    "totals": reliability.get("signature", {}).get("totals", {}),
                },
            )

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
    class OpsApiHandler(BaseHTTPRequestHandler):
        server_version = "SupportAgentOpsAPI/1.0"

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PATCH(self) -> None:
            self._dispatch("PATCH")

        def do_DELETE(self) -> None:
            self._dispatch("DELETE")

        def _dispatch(self, method: str) -> None:
            parsed = urlparse(self.path)
            query = {
                key: values[-1]
                for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
                if values
            }
            request_id = self.headers.get("X-Request-Id")
            body: dict[str, Any] | None = None
            if method in {"POST", "PATCH"}:
                body = self._read_json_body()
                if body is None:
                    response = _error(
                        _request_id(request_id),
                        code="invalid_json",
                        message="request body must be a JSON object",
                    )
                    self._write_json(response.status, response.payload)
                    return

            response = handle_api_request(
                runtime,
                method=method,
                path=parsed.path,
                query=query,
                body=body,
                request_id=request_id,
            )
            self._write_json(response.status, response.payload)

        def _read_json_body(self) -> dict[str, Any] | None:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return {}
            try:
                length = int(raw_length)
            except ValueError:
                return None
            if length <= 0:
                return {}
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                return None
            if not isinstance(payload, dict):
                return None
            return payload

        def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    return OpsApiHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run support-agent Ops API server")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="HTTP bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP bind port")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
                "contract": "api-contract-v1",
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
