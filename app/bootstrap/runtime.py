from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.application.session_service import SessionContextStoreProtocol, SessionService
from app.domain.conversation.conversation_state import ConversationMode, ConversationState
from app.domain.ticket.ticket_api import TicketAPI as TicketAPIV2
from app.domain.ticket.ticket_workflow_state import (
    ApprovalState,
    HandoffState,
    TicketWorkflowState,
)
from config import AppConfig, load_app_config
from core.hitl.approval_policy import ApprovalPolicy
from core.hitl.approval_runtime import ApprovalRuntime
from core.recommended_actions_engine import RecommendedActionsEngine
from core.retriever import Retriever
from core.summary_engine import SummaryEngine
from core.ticket_api import TicketAPI as LegacyTicketAPI
from core.trace_logger import JsonTraceLogger
from llm import build_summary_model_adapter
from openclaw_adapter.bindings import build_default_bindings
from openclaw_adapter.gateway import OpenClawGateway
from openclaw_adapter.session_mapper import SessionMapper
from runtime.agents import AgentRegistry, build_default_agent_registry
from runtime.tools import ToolRegistry, build_default_tool_registry
from storage.ticket_repository import TicketRepository


@dataclass(frozen=True)
class OpsApiBootstrap:
    app_config: AppConfig
    gateway: OpenClawGateway
    repository: TicketRepository
    ticket_api: LegacyTicketAPI
    ticket_api_v2: TicketAPIV2
    trace_logger: JsonTraceLogger
    retriever: Retriever
    summary_engine: SummaryEngine
    recommendation_engine: RecommendedActionsEngine
    tool_registry: ToolRegistry
    agent_registry: AgentRegistry
    approval_runtime: ApprovalRuntime
    kb_store_path: Path


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
        handoff_state = _normalize_handoff_state(ticket.handoff_state)
        approval_state = _normalize_approval_state(ticket.handoff_state)
        return TicketWorkflowState(
            ticket_id=ticket.ticket_id,
            status=ticket.status,
            handoff_state=handoff_state,
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


def _conversation_mode_from_session_context(raw_mode: str) -> ConversationMode:
    mode = raw_mode.strip().lower()
    if mode in {"faq"}:
        return "faq"
    if mode in {"single_issue", "multi_issue", "support"}:
        return "support"
    return "idle"


def _normalize_handoff_state(raw_state: str) -> HandoffState:
    state = raw_state.strip().lower()
    if state == "requested":
        return "pending_claim"
    if state == "accepted":
        return "claimed"
    if state == "none":
        return "none"
    if state == "pending_claim":
        return "pending_claim"
    if state == "claimed":
        return "claimed"
    if state == "in_progress":
        return "in_progress"
    if state == "waiting_customer":
        return "waiting_customer"
    if state == "completed":
        return "completed"
    return "none"


def _normalize_approval_state(raw_state: str) -> ApprovalState:
    state = raw_state.strip().lower()
    if state == "pending_approval":
        return "pending_approval"
    if state == "approved":
        return "approved"
    if state == "rejected":
        return "rejected"
    if state == "timeout":
        return "timeout"
    return "none"


def _session_mode_from_conversation_mode(mode: ConversationMode) -> str:
    if mode == "faq":
        return "single_issue"
    if mode == "support":
        return "multi_issue"
    return "awaiting_new_issue"


def _default_kb_store_path(app_config: AppConfig) -> Path:
    return Path(app_config.storage.sqlite_path).with_name("ops_api_kb.json")


def build_ops_api_bootstrap(environment: str | None, *, seed_root: Path) -> OpsApiBootstrap:
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
    retriever = Retriever(seed_root)
    summary_engine = SummaryEngine(model_adapter=build_summary_model_adapter(app_config.llm))
    recommendation_engine = RecommendedActionsEngine()
    tool_registry = build_default_tool_registry()
    agent_registry = build_default_agent_registry()
    approval_runtime = ApprovalRuntime(
        ticket_api=ticket_api,
        policy=ApprovalPolicy.default(),
        trace_logger=bindings.trace_logger,
    )

    return OpsApiBootstrap(
        app_config=app_config,
        gateway=gateway,
        repository=repository,
        ticket_api=ticket_api,
        ticket_api_v2=ticket_api_v2,
        trace_logger=bindings.trace_logger,
        retriever=retriever,
        summary_engine=summary_engine,
        recommendation_engine=recommendation_engine,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        approval_runtime=approval_runtime,
        kb_store_path=_default_kb_store_path(app_config),
    )
