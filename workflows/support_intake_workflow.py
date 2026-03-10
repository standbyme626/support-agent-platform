from __future__ import annotations

from dataclasses import dataclass

from core.ticket_api import TicketAPI
from core.workflow_engine import WorkflowEngine, WorkflowOutcome
from storage.models import InboundEnvelope

from .case_collab_workflow import CaseCollabWorkflow


@dataclass(frozen=True)
class SupportIntakeResult:
    ticket_id: str
    reply_text: str
    handoff: bool
    collab_push: dict[str, str] | None
    outcome: WorkflowOutcome
    ticket_action: str
    summary: str
    recommended_actions: list[str]
    handoff_required: bool
    queue: str
    priority: str
    trace_events: list[str]


class SupportIntakeWorkflow:
    """Workflow A: intake entry -> FAQ reply -> auto-ticket -> handoff."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        *,
        case_collab_workflow: CaseCollabWorkflow | None = None,
        ticket_api: TicketAPI | None = None,
        intent_confidence_threshold: float = 0.58,
        faq_score_threshold: float = 0.20,
        handoff_confidence_threshold: float = 0.45,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._case_collab_workflow = case_collab_workflow
        self._ticket_api = ticket_api or getattr(case_collab_workflow, "_ticket_api", None)
        self._intent_confidence_threshold = intent_confidence_threshold
        self._faq_score_threshold = faq_score_threshold
        self._handoff_confidence_threshold = handoff_confidence_threshold

    def run(
        self,
        envelope: InboundEnvelope,
        *,
        existing_ticket_id: str | None = None,
    ) -> SupportIntakeResult:
        outcome = self._workflow_engine.process_intake(
            envelope,
            existing_ticket_id=existing_ticket_id,
        )
        self._record_intake_trace(envelope, outcome)

        collab_push: dict[str, str] | None = None
        if self._should_push_to_collab(outcome, existing_ticket_id):
            if self._case_collab_workflow is None:
                raise RuntimeError("CaseCollabWorkflow is required for collaboration push")
            collab_push = self._case_collab_workflow.push_new_ticket(outcome.ticket.ticket_id)

        ticket_action, trace_events = self._derive_ticket_action(outcome)
        recommended_actions = [item.action for item in outcome.recommendations]

        return SupportIntakeResult(
            ticket_id=outcome.ticket.ticket_id,
            reply_text=outcome.reply_text,
            handoff=outcome.handoff.should_handoff,
            collab_push=collab_push,
            outcome=outcome,
            ticket_action=ticket_action,
            summary=outcome.summary,
            recommended_actions=recommended_actions,
            handoff_required=outcome.handoff.should_handoff,
            queue=outcome.ticket.queue,
            priority=outcome.ticket.priority,
            trace_events=trace_events,
        )

    def _should_push_to_collab(
        self,
        outcome: WorkflowOutcome,
        existing_ticket_id: str | None,
    ) -> bool:
        if self._case_collab_workflow is None:
            return False
        if existing_ticket_id is not None:
            return False
        if outcome.ticket.queue == "faq":
            return False
        return True

    def _record_intake_trace(self, envelope: InboundEnvelope, outcome: WorkflowOutcome) -> None:
        if self._ticket_api is None:
            return

        ticket_id = outcome.ticket.ticket_id
        lifecycle_stage = (
            "awaiting_human" if outcome.handoff.should_handoff else "drafted"
        )
        self._ticket_api.update_ticket(
            ticket_id,
            {
                "inbox": str(envelope.metadata.get("inbox") or outcome.ticket.inbox),
                "lifecycle_stage": lifecycle_stage,
                "first_response_due_at": outcome.sla.first_response_due_at,
                "resolution_due_at": outcome.sla.resolution_due_at,
            },
            actor_id="support-intake",
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_classified",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "intent": outcome.intent.intent,
                "confidence": outcome.intent.confidence,
                "reason": outcome.intent.reason,
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_context_retrieved",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "source_type": "faq" if outcome.intent.intent == "faq" else "grounded",
                "source_breakdown": sorted({doc.source_type for doc in outcome.retrieved_docs}),
                "doc_ids": [doc.doc_id for doc in outcome.retrieved_docs],
                "doc_titles": [doc.title for doc in outcome.retrieved_docs],
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_draft_generated",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "reply_preview": outcome.reply_text[:200],
                "should_handoff": outcome.handoff.should_handoff,
            },
        )
        if outcome.handoff.should_handoff:
            self._ticket_api.add_event(
                ticket_id,
                event_type="ticket_handoff_requested",
                actor_type="agent",
                actor_id="support-intake",
                payload={
                    "reason": outcome.handoff.reason,
                    "sla_targets": outcome.sla.escalation_targets,
                },
            )

    def _derive_ticket_action(self, outcome: WorkflowOutcome) -> tuple[str, list[str]]:
        trace_events: list[str] = []
        if outcome.handoff.should_handoff:
            trace_events.extend(["need_handoff", "push_human_queue"])
            return "handoff", trace_events

        if outcome.intent.is_low_confidence or (
            outcome.intent.confidence < self._handoff_confidence_threshold
        ):
            trace_events.extend(["low_confidence", "conservative_ticket"])
            return "conservative_ticket", trace_events

        if outcome.intent.intent == "faq":
            top_score = outcome.retrieved_docs[0].score if outcome.retrieved_docs else 0.0
            if top_score < self._faq_score_threshold:
                trace_events.extend(["faq_weak_hit", "conservative_ticket"])
                return "conservative_ticket", trace_events
            trace_events.extend(["faq_hit", "direct_reply"])
            return "faq_reply", trace_events

        if outcome.ticket.status == "escalated":
            trace_events.extend(["status_escalated", "notify_collab"])
            return "escalate", trace_events

        if outcome.intent.confidence < self._intent_confidence_threshold:
            trace_events.extend(["below_intent_threshold", "conservative_ticket"])
            return "conservative_ticket", trace_events

        trace_events.extend(["create_ticket", "notify_collab"])
        return "create_ticket", trace_events
