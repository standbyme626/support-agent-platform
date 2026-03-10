from __future__ import annotations

from dataclasses import dataclass

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
    ) -> None:
        self._workflow_engine = workflow_engine
        self._case_collab_workflow = case_collab_workflow

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
