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


class SupportIntakeWorkflow:
    """Workflow A: intake entry -> FAQ reply -> auto-ticket -> handoff."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        *,
        case_collab_workflow: CaseCollabWorkflow | None = None,
        ticket_api: TicketAPI | None = None,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._case_collab_workflow = case_collab_workflow
        self._ticket_api = ticket_api or getattr(case_collab_workflow, "_ticket_api", None)

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

        return SupportIntakeResult(
            ticket_id=outcome.ticket.ticket_id,
            reply_text=outcome.reply_text,
            handoff=outcome.handoff.should_handoff,
            collab_push=collab_push,
            outcome=outcome,
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
            event_type="classify_decision",
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
            event_type="retrieve_context",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "source_type": "faq" if outcome.intent.intent == "faq" else "sop",
                "doc_ids": [doc.doc_id for doc in outcome.retrieved_docs],
                "doc_titles": [doc.title for doc in outcome.retrieved_docs],
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="draft_response",
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
                event_type="escalate_recommended",
                actor_type="agent",
                actor_id="support-intake",
                payload={
                    "reason": outcome.handoff.reason,
                    "sla_targets": outcome.sla.escalation_targets,
                },
            )
