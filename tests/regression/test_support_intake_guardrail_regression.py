from __future__ import annotations

from pathlib import Path

from core.handoff_manager import HandoffManager
from core.intent_router import IntentRouter
from core.recommended_actions_engine import RecommendedActionsEngine
from core.retriever import Retriever
from core.sla_engine import SlaEngine
from core.summary_engine import SummaryEngine
from core.ticket_api import TicketAPI
from core.tool_router import ToolRouter
from core.workflow_engine import WorkflowEngine
from storage.models import InboundEnvelope
from storage.ticket_repository import TicketRepository
from workflows.case_collab_workflow import CaseCollabWorkflow
from workflows.support_intake_workflow import SupportIntakeWorkflow


def _build_intake(tmp_path: Path) -> SupportIntakeWorkflow:
    repo = TicketRepository(tmp_path / "tickets.db")
    repo.apply_migrations()
    ticket_api = TicketAPI(repo)

    tool_router = ToolRouter(
        ticket_api=ticket_api,
        retriever=Retriever(Path(__file__).resolve().parents[2] / "seed_data"),
    )
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "seed_data"
        / "sla_rules"
        / "default_sla_rules.json"
    )
    engine = WorkflowEngine(
        ticket_api=ticket_api,
        intent_router=IntentRouter(),
        tool_router=tool_router,
        summary_engine=SummaryEngine(),
        handoff_manager=HandoffManager.from_file(policy_path),
        sla_engine=SlaEngine.from_file(policy_path),
        recommendation_engine=RecommendedActionsEngine(),
    )
    return SupportIntakeWorkflow(engine, case_collab_workflow=CaseCollabWorkflow(ticket_api))


def test_low_confidence_message_goes_conservative_regression(tmp_path: Path) -> None:
    workflow = _build_intake(tmp_path)
    result = workflow.run(
        InboundEnvelope(
            channel="telegram",
            session_id="reg-low-confidence",
            message_text="??? @@ ###",
            metadata={"thread_id": "thread-reg-low-confidence"},
        )
    )

    assert result.handoff_required is True
    assert result.ticket_action == "handoff"
    assert "need_handoff" in result.trace_events
    assert "转接人工客服" in result.reply_text
