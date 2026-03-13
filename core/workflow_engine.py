from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from storage.models import InboundEnvelope, KBDocument, Ticket

from .disambiguation import DisambiguationResult, NewIssueDetector
from .handoff_manager import HandoffDecision, HandoffManager
from .intent_router import IntentDecision, IntentRouter
from .recommended_actions_engine import RecommendedAction, RecommendedActionsEngine
from .reply_generator import ReplyGenerator
from .reply_orchestration import ReplyGenerationType
from .sla_engine import SlaCheckResult, SlaEngine
from .summary_engine import SummaryEngine
from .ticket_api import TicketAPI
from .tool_router import ToolRouter
from .trace_logger import JsonTraceLogger, new_trace_id


@dataclass(frozen=True)
class WorkflowOutcome:
    ticket: Ticket
    intent: IntentDecision
    resolved_existing_ticket_id: str | None
    retrieved_docs: list[KBDocument]
    summary: str
    llm_trace: dict[str, object]
    recommendations: list[RecommendedAction]
    handoff: HandoffDecision
    sla: SlaCheckResult
    reply_text: str
    reply_trace: dict[str, object]
    reply_generation_type: str


class WorkflowEngine:
    """Workflow-first orchestrator for core business rules (G-Q)."""

    _TICKET_ID_PATTERN = re.compile(r"\b(?:TCK-[A-Za-z0-9_-]+|TICKET-[A-Za-z0-9_-]+)\b")
    _PROGRESS_KEYWORDS = ("进度", "跟进", "到哪", "状态", "处理到哪", "什么时候", "查询工单")
    _CONSULTING_INTENTS = frozenset({"greeting", "faq"})

    def __init__(
        self,
        *,
        ticket_api: TicketAPI,
        intent_router: IntentRouter,
        tool_router: ToolRouter,
        summary_engine: SummaryEngine,
        handoff_manager: HandoffManager,
        sla_engine: SlaEngine,
        recommendation_engine: RecommendedActionsEngine,
        trace_logger: JsonTraceLogger | None = None,
        reply_generator: ReplyGenerator | None = None,
        new_issue_detector: NewIssueDetector | None = None,
    ) -> None:
        self._ticket_api = ticket_api
        self._intent_router = intent_router
        self._tool_router = tool_router
        self._summary_engine = summary_engine
        self._handoff_manager = handoff_manager
        self._sla_engine = sla_engine
        self._recommendation_engine = recommendation_engine
        self._trace_logger = trace_logger
        self._reply_generator = reply_generator or ReplyGenerator()
        self._new_issue_detector = new_issue_detector or NewIssueDetector()

    def process_intake(
        self,
        envelope: InboundEnvelope,
        existing_ticket_id: str | None = None,
        *,
        force_new_ticket: bool = False,
    ) -> WorkflowOutcome:
        trace_id = str(envelope.metadata.get("trace_id") or new_trace_id())
        if force_new_ticket:
            resolved_existing_ticket_id = None
        else:
            resolved_existing_ticket_id = self.resolve_existing_ticket_id(
                envelope,
                requested_ticket_id=existing_ticket_id,
            )
        intent = self._intent_router.route(envelope.message_text)
        self._log(
            "route_decision",
            {
                "intent": intent.intent,
                "confidence": intent.confidence,
                "is_low_confidence": intent.is_low_confidence,
                "reason": intent.reason,
            },
            trace_id=trace_id,
            session_id=envelope.session_id,
            ticket_id=resolved_existing_ticket_id,
        )
        kb_source = "faq" if intent.intent in {"faq", "greeting"} else "grounded"
        docs_result = self._tool_router.execute(
            "search_kb",
            {
                "source_type": kb_source,
                "query": envelope.message_text,
                "top_k": 3,
                "trace_id": trace_id,
                "session_id": envelope.session_id,
            },
        )
        retrieved_docs = self._normalize_docs(docs_result.output)

        if resolved_existing_ticket_id is None:
            is_consulting = (
                intent.intent in self._CONSULTING_INTENTS and not intent.is_low_confidence
            )
            if is_consulting:
                consulting_ticket = self._find_recent_consulting_ticket(envelope.session_id)
                if consulting_ticket is None:
                    ticket = self._ticket_api.create_ticket(
                        channel=envelope.channel,
                        session_id=envelope.session_id,
                        thread_id=str(envelope.metadata.get("thread_id") or envelope.session_id),
                        title="问候咨询" if intent.intent == "greeting" else "FAQ咨询",
                        latest_message=envelope.message_text,
                        intent=intent.intent,
                        priority="P4",
                        queue="faq",
                        metadata={
                            **envelope.metadata,
                            "trace_id": trace_id,
                            "last_intent": intent.intent,
                            "session_mode": "faq_consulting",
                        },
                    )
                    self._log(
                        "consulting_ticket_created",
                        {
                            "ticket_id": ticket.ticket_id,
                            "intent": intent.intent,
                            "consulting_mode": "create",
                        },
                        trace_id=trace_id,
                        ticket_id=ticket.ticket_id,
                        session_id=ticket.session_id,
                    )
                else:
                    ticket = self._ticket_api.update_ticket(
                        consulting_ticket.ticket_id,
                        {
                            "latest_message": envelope.message_text,
                            "intent": intent.intent,
                            "metadata": {
                                **envelope.metadata,
                                "trace_id": trace_id,
                                "last_intent": intent.intent,
                                "session_mode": "faq_consulting",
                            },
                        },
                        actor_id="workflow-engine",
                    )
                    self._ticket_api.bind_session_ticket(
                        envelope.session_id,
                        ticket.ticket_id,
                        metadata={
                            "trace_id": trace_id,
                            "last_intent": intent.intent,
                            "session_mode": "faq_consulting",
                        },
                    )
                    self._log(
                        "consulting_ticket_reused",
                        {
                            "ticket_id": ticket.ticket_id,
                            "intent": intent.intent,
                            "consulting_mode": "reuse",
                        },
                        trace_id=trace_id,
                        ticket_id=ticket.ticket_id,
                        session_id=ticket.session_id,
                    )
            else:
                ticket = self._ticket_api.create_ticket(
                    channel=envelope.channel,
                    session_id=envelope.session_id,
                    thread_id=str(envelope.metadata.get("thread_id") or envelope.session_id),
                    title=envelope.message_text[:24] or "客户咨询",
                    latest_message=envelope.message_text,
                    intent=intent.intent,
                    priority="P2" if intent.intent in {"repair", "billing"} else "P3",
                    queue="support",
                    metadata={
                        **envelope.metadata,
                        "trace_id": trace_id,
                        "last_intent": intent.intent,
                    },
                )
        else:
            ticket = self._ticket_api.update_ticket(
                resolved_existing_ticket_id,
                {"latest_message": envelope.message_text, "intent": intent.intent},
                actor_id="workflow-engine",
            )
            self._ticket_api.bind_session_ticket(
                envelope.session_id,
                ticket.ticket_id,
                metadata={
                    "trace_id": trace_id,
                    "last_intent": intent.intent,
                    "session_mode": "multi_issue"
                    if envelope.metadata.get("recent_ticket_ids")
                    else "single_issue",
                },
            )

        events = self._ticket_api.list_events(ticket.ticket_id)
        summary = self._summary_engine.case_summary(ticket, events)
        llm_trace = {
            key: value
            for key, value in self._summary_engine.last_generation_metadata().items()
        }
        self._log(
            "summary_generated",
            {
                "summary_preview": summary[:200],
                **llm_trace,
            },
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=ticket.session_id,
        )
        sla_result = self._sla_engine.evaluate(ticket, events)
        self._log(
            "sla_evaluated",
            {
                "breached_items": sla_result.breached_items,
                "escalation_targets": sla_result.escalation_targets,
                "first_response_due_at": sla_result.first_response_due_at.isoformat(),
                "resolution_due_at": sla_result.resolution_due_at.isoformat(),
                "policy_version": sla_result.policy_version,
                "matched_rule_id": sla_result.matched_rule_id,
                "matched_rule_path": sla_result.matched_rule_path,
                "used_fallback": sla_result.used_fallback,
            },
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=ticket.session_id,
        )

        recommendations = self._recommendation_engine.recommend(
            ticket=ticket,
            intent=intent,
            retrieved_docs=retrieved_docs,
            sla_breaches=sla_result.breached_items,
        )
        self._log(
            "recommended_actions",
            {"actions": [item.as_dict() for item in recommendations]},
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=ticket.session_id,
        )

        handoff_decision = self._handoff_manager.evaluate(
            ticket=ticket,
            intent=intent,
            case_summary=summary,
            recommendations=recommendations,
            recent_events=events,
            sla_result=sla_result,
        )
        self._log(
            "handoff_decision",
            {
                "should_handoff": handoff_decision.should_handoff,
                "reason": handoff_decision.reason,
                "policy_version": handoff_decision.policy_version,
                "matched_rule_paths": list(handoff_decision.matched_rule_paths),
            },
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=ticket.session_id,
        )
        if handoff_decision.should_handoff:
            ticket = self._handoff_manager.mark_handoff(
                ticket_api=self._ticket_api,
                ticket_id=ticket.ticket_id,
                decision=handoff_decision,
            )

        fallback_reply = self._build_reply(
            intent,
            retrieved_docs,
            handoff_decision,
            ticket=ticket,
            latest_event_types=[event.event_type for event in events[-5:]],
        )
        disambiguation_decision = (
            str(envelope.metadata.get("disambiguation_decision") or "").strip() or None
        )
        disambiguation_reason = (
            str(envelope.metadata.get("disambiguation_reason") or "").strip() or None
        )
        reply_result = self._reply_generator.generate(
            message_text=envelope.message_text,
            intent=intent,
            ticket=ticket,
            retrieved_docs=retrieved_docs,
            summary=summary,
            recommendations=recommendations,
            handoff=handoff_decision,
            events=events,
            fallback_reply=fallback_reply,
            session_mode=self._session_mode_from_metadata(envelope.metadata),
            disambiguation_decision=disambiguation_decision,
            disambiguation_reason=disambiguation_reason,
            forced_generation_type=self._reply_generation_hint_from_metadata(envelope.metadata),
        )
        self._log(
            "reply_generated",
            {
                **reply_result.metadata,
                "reply_preview": reply_result.reply_text[:200],
                "workflow": "support-intake",
            },
            trace_id=trace_id,
            ticket_id=ticket.ticket_id,
            session_id=ticket.session_id,
        )

        return WorkflowOutcome(
            ticket=ticket,
            intent=intent,
            resolved_existing_ticket_id=resolved_existing_ticket_id,
            retrieved_docs=retrieved_docs,
            summary=summary,
            llm_trace=llm_trace,
            recommendations=recommendations,
            handoff=handoff_decision,
            sla=sla_result,
            reply_text=reply_result.reply_text,
            reply_trace={key: value for key, value in reply_result.metadata.items()},
            reply_generation_type=reply_result.generation_type,
        )

    def assess_disambiguation(
        self,
        envelope: InboundEnvelope,
        *,
        requested_ticket_id: str | None,
    ) -> DisambiguationResult:
        ticket_candidates = self._ticket_candidates_from_metadata(envelope.metadata)
        active_ticket_id = self._active_ticket_from_metadata(envelope.metadata)
        if active_ticket_id is None and ticket_candidates:
            active_ticket_id = ticket_candidates[0]
        active_ticket = self._ticket_api.get_ticket(active_ticket_id) if active_ticket_id else None
        intent = self._intent_router.route(envelope.message_text)
        return self._new_issue_detector.evaluate(
            message_text=envelope.message_text,
            intent=intent,
            candidate_ticket_ids=ticket_candidates,
            active_ticket_id=active_ticket_id,
            requested_ticket_id=requested_ticket_id,
            session_mode=self._session_mode_from_metadata(envelope.metadata),
            last_intent=self._last_intent_from_metadata(envelope.metadata),
            active_ticket=active_ticket,
        )

    def resolve_existing_ticket_id(
        self,
        envelope: InboundEnvelope,
        *,
        requested_ticket_id: str | None,
    ) -> str | None:
        ticket_candidates = self._ticket_candidates_from_metadata(envelope.metadata)
        explicit_ticket_id = self._extract_ticket_id_from_text(envelope.message_text)
        if explicit_ticket_id and explicit_ticket_id in ticket_candidates:
            return explicit_ticket_id

        normalized_requested = str(requested_ticket_id or "").strip() or None
        if normalized_requested:
            return normalized_requested

        if self._is_progress_query_text(envelope.message_text):
            active_ticket_id = str(envelope.metadata.get("active_ticket_id") or "").strip() or None
            if active_ticket_id:
                return active_ticket_id

        if ticket_candidates:
            return ticket_candidates[0]
        return None

    def _log(
        self,
        event_type: str,
        payload: dict[str, object],
        *,
        trace_id: str,
        session_id: str,
        ticket_id: str | None = None,
    ) -> None:
        if self._trace_logger is None:
            return
        self._trace_logger.log(
            event_type,
            payload,
            trace_id=trace_id,
            ticket_id=ticket_id,
            session_id=session_id,
        )

    @staticmethod
    def _normalize_docs(raw_docs: object) -> list[KBDocument]:
        if not isinstance(raw_docs, list):
            return []

        docs: list[KBDocument] = []
        for item in raw_docs:
            if isinstance(item, KBDocument):
                docs.append(item)
                continue
            if isinstance(item, dict):
                docs.append(
                    KBDocument(
                        doc_id=str(item.get("doc_id", "")),
                        source_type=str(item.get("source_type", "")),
                        title=str(item.get("title", "")),
                        content=str(item.get("content", "")),
                        tags=[str(tag) for tag in item.get("tags", [])],
                        score=float(item.get("score", 0.0)),
                    )
                )
        return docs

    @staticmethod
    def _build_reply(
        intent: IntentDecision,
        retrieved_docs: list[KBDocument],
        handoff: HandoffDecision,
        *,
        ticket: Ticket | None = None,
        latest_event_types: list[str] | None = None,
    ) -> str:
        if handoff.should_handoff:
            if ticket is not None:
                return (
                    f"已为你转接人工客服并发起人工接管，工单{ticket.ticket_id}当前状态为{ticket.status}。"
                    "处理人员会尽快联系你，请保持会话畅通。"
                )
            return "已为你转接人工客服，请稍候。"

        if intent.intent == "progress_query":
            if ticket is None:
                return "已收到进度查询，请提供工单号（例如 TCK-00001）或在原会话继续追问。"
            assignee = ticket.assignee or "当前待认领"
            recent = ",".join(latest_event_types or []) or "暂无事件"
            return (
                f"工单{ticket.ticket_id}当前状态：{ticket.status}，负责人：{assignee}。"
                f"最近进展：{recent}。我们会继续同步后续处理情况。"
            )

        if intent.intent == "greeting":
            return "你好，我是智慧工单助手。请描述你的问题（如报修、账单、投诉），我来帮你处理。"

        if intent.intent == "faq" and retrieved_docs:
            doc = retrieved_docs[0]
            return f"参考{doc.title}：{doc.content}"

        if intent.is_low_confidence:
            return "我需要更多信息来准确处理，请补充订单号或故障截图。"

        if retrieved_docs:
            evidence = ", ".join(f"{doc.source_type}:{doc.doc_id}" for doc in retrieved_docs[:2])
            return f"已收到，我们正在处理你的工单。参考证据：{evidence}"
        return "已收到，我们正在处理你的工单。"

    @classmethod
    def _ticket_candidates_from_metadata(cls, metadata: dict[str, object]) -> list[str]:
        active_ticket_id = str(
            metadata.get("active_ticket_id") or metadata.get("ticket_id") or ""
        ).strip()
        raw_recent_ticket_ids = metadata.get("recent_ticket_ids")
        recent_ticket_ids = (
            [
                str(item).strip()
                for item in raw_recent_ticket_ids
                if str(item).strip()
            ]
            if isinstance(raw_recent_ticket_ids, list)
            else []
        )
        raw_session_context = metadata.get("session_context")
        if isinstance(raw_session_context, dict):
            context_active = str(raw_session_context.get("active_ticket_id") or "").strip()
            if context_active:
                active_ticket_id = context_active
            context_recent = raw_session_context.get("recent_ticket_ids")
            if isinstance(context_recent, list):
                recent_ticket_ids.extend(
                    [str(item).strip() for item in context_recent if str(item).strip()]
                )

        ticket_ids: list[str] = []
        seen: set[str] = set()
        for candidate in [active_ticket_id, *recent_ticket_ids]:
            ticket_id = str(candidate).strip()
            if not ticket_id or ticket_id in seen:
                continue
            ticket_ids.append(ticket_id)
            seen.add(ticket_id)
        return ticket_ids

    @classmethod
    def _extract_ticket_id_from_text(cls, message_text: str) -> str | None:
        match = cls._TICKET_ID_PATTERN.search(message_text)
        if match is None:
            return None
        return str(match.group(0)).strip() or None

    @classmethod
    def _active_ticket_from_metadata(cls, metadata: dict[str, object]) -> str | None:
        raw_session_context = metadata.get("session_context")
        if isinstance(raw_session_context, dict):
            context_active = str(raw_session_context.get("active_ticket_id") or "").strip()
            if context_active:
                return context_active
        active_ticket_id = str(
            metadata.get("active_ticket_id") or metadata.get("ticket_id") or ""
        ).strip()
        return active_ticket_id or None

    @classmethod
    def _session_mode_from_metadata(cls, metadata: dict[str, object]) -> str | None:
        raw_session_context = metadata.get("session_context")
        if isinstance(raw_session_context, dict):
            context_mode = str(raw_session_context.get("session_mode") or "").strip()
            if context_mode:
                return context_mode
        session_mode = str(metadata.get("session_mode") or "").strip()
        return session_mode or None

    @classmethod
    def _last_intent_from_metadata(cls, metadata: dict[str, object]) -> str | None:
        raw_session_context = metadata.get("session_context")
        if isinstance(raw_session_context, dict):
            context_last_intent = str(raw_session_context.get("last_intent") or "").strip()
            if context_last_intent:
                return context_last_intent
        last_intent = str(metadata.get("last_intent") or "").strip()
        return last_intent or None

    @classmethod
    def _is_progress_query_text(cls, message_text: str) -> bool:
        text = message_text.strip()
        if not text:
            return False
        lowered = text.lower()
        if "progress" in lowered:
            return True
        return any(keyword in text for keyword in cls._PROGRESS_KEYWORDS)

    def _find_recent_consulting_ticket(self, session_id: str) -> Ticket | None:
        candidates = [
            item
            for item in self._ticket_api.list_all_tickets(limit=2000)
            if item.session_id == session_id
            and item.intent in self._CONSULTING_INTENTS
            and item.queue == "faq"
            and item.status != "closed"
        ]
        if not candidates:
            return None
        min_dt = datetime.min.replace(tzinfo=UTC)
        candidates.sort(key=lambda item: item.updated_at or min_dt, reverse=True)
        return candidates[0]

    @classmethod
    def _reply_generation_hint_from_metadata(
        cls, metadata: dict[str, object]
    ) -> ReplyGenerationType | None:
        raw_hint = str(metadata.get("reply_generation_hint") or "").strip()
        if raw_hint in {"faq", "progress", "handoff", "generic", "disambiguation", "switch"}:
            return cast(ReplyGenerationType, raw_hint)
        return None
