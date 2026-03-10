from __future__ import annotations

from dataclasses import dataclass

from storage.models import InboundEnvelope, KBDocument, Ticket

from .handoff_manager import HandoffDecision, HandoffManager
from .intent_router import IntentDecision, IntentRouter
from .recommended_actions_engine import RecommendedAction, RecommendedActionsEngine
from .sla_engine import SlaCheckResult, SlaEngine
from .summary_engine import SummaryEngine
from .ticket_api import TicketAPI
from .tool_router import ToolRouter
from .trace_logger import JsonTraceLogger, new_trace_id


@dataclass(frozen=True)
class WorkflowOutcome:
    ticket: Ticket
    intent: IntentDecision
    retrieved_docs: list[KBDocument]
    summary: str
    recommendations: list[RecommendedAction]
    handoff: HandoffDecision
    sla: SlaCheckResult
    reply_text: str


class WorkflowEngine:
    """Workflow-first orchestrator for core business rules (G-Q)."""

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
    ) -> None:
        self._ticket_api = ticket_api
        self._intent_router = intent_router
        self._tool_router = tool_router
        self._summary_engine = summary_engine
        self._handoff_manager = handoff_manager
        self._sla_engine = sla_engine
        self._recommendation_engine = recommendation_engine
        self._trace_logger = trace_logger

    def process_intake(
        self, envelope: InboundEnvelope, existing_ticket_id: str | None = None
    ) -> WorkflowOutcome:
        trace_id = str(envelope.metadata.get("trace_id") or new_trace_id())
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
            ticket_id=existing_ticket_id,
        )
        kb_source = "faq" if intent.intent == "faq" else "grounded"
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

        if existing_ticket_id is None:
            if intent.intent == "faq" and not intent.is_low_confidence and retrieved_docs:
                ticket = self._ticket_api.create_ticket(
                    channel=envelope.channel,
                    session_id=envelope.session_id,
                    thread_id=str(envelope.metadata.get("thread_id") or envelope.session_id),
                    title="FAQ咨询",
                    latest_message=envelope.message_text,
                    intent=intent.intent,
                    priority="P4",
                    queue="faq",
                    metadata={**envelope.metadata, "trace_id": trace_id},
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
                    metadata={**envelope.metadata, "trace_id": trace_id},
                )
        else:
            ticket = self._ticket_api.update_ticket(
                existing_ticket_id,
                {"latest_message": envelope.message_text, "intent": intent.intent},
                actor_id="workflow-engine",
            )

        events = self._ticket_api.list_events(ticket.ticket_id)
        summary = self._summary_engine.case_summary(ticket, events)
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

        reply_text = self._build_reply(intent, retrieved_docs, handoff_decision)

        return WorkflowOutcome(
            ticket=ticket,
            intent=intent,
            retrieved_docs=retrieved_docs,
            summary=summary,
            recommendations=recommendations,
            handoff=handoff_decision,
            sla=sla_result,
            reply_text=reply_text,
        )

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
    ) -> str:
        if handoff.should_handoff:
            return "已为你转接人工客服，请稍候。"

        if intent.intent == "faq" and retrieved_docs:
            doc = retrieved_docs[0]
            return f"参考{doc.title}：{doc.content}"

        if intent.is_low_confidence:
            return "我需要更多信息来准确处理，请补充订单号或故障截图。"

        if retrieved_docs:
            evidence = ", ".join(f"{doc.source_type}:{doc.doc_id}" for doc in retrieved_docs[:2])
            return f"已收到，我们正在处理你的工单。参考证据：{evidence}"
        return "已收到，我们正在处理你的工单。"
