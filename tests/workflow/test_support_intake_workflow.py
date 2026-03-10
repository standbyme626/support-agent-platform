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


def _build_intake_workflow(tmp_path: Path) -> tuple[SupportIntakeWorkflow, TicketAPI]:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    ticket_api = TicketAPI(repo)
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    tool_router = ToolRouter(ticket_api=ticket_api, retriever=retriever)

    engine = WorkflowEngine(
        ticket_api=ticket_api,
        intent_router=IntentRouter(),
        tool_router=tool_router,
        summary_engine=SummaryEngine(),
        handoff_manager=HandoffManager(),
        sla_engine=SlaEngine.from_file(
            Path(__file__).resolve().parents[2]
            / "seed_data"
            / "sla_rules"
            / "default_sla_rules.json"
        ),
        recommendation_engine=RecommendedActionsEngine(),
    )

    return (
        SupportIntakeWorkflow(engine, case_collab_workflow=CaseCollabWorkflow(ticket_api)),
        ticket_api,
    )


def test_support_intake_faq_reply_and_no_collab_push(tmp_path: Path) -> None:
    workflow, _ = _build_intake_workflow(tmp_path)
    result = workflow.run(
        InboundEnvelope(
            channel="telegram",
            session_id="session-faq",
            message_text="如何 查询 工单 进度",
            metadata={"thread_id": "thread-faq"},
        )
    )

    assert result.ticket_id.startswith("TCK-")
    assert "参考" in result.reply_text
    assert result.collab_push is None


def test_support_intake_repair_creates_ticket_and_pushes_collab(tmp_path: Path) -> None:
    workflow, ticket_api = _build_intake_workflow(tmp_path)
    result = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-repair",
            message_text="设备故障报修",
            metadata={"thread_id": "thread-repair"},
        )
    )

    assert result.outcome.ticket.intent == "repair"
    assert result.collab_push is not None
    assert "/claim" in result.collab_push["message"]
    assert "/resolve" in result.collab_push["message"]

    events = ticket_api.list_events(result.ticket_id)
    event_types = {event.event_type for event in events}
    assert "classify_decision" in event_types
    assert "retrieve_context" in event_types
    assert "draft_response" in event_types
