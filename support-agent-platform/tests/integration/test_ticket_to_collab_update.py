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
from core.trace_logger import JsonTraceLogger
from core.workflow_engine import WorkflowEngine
from storage.models import InboundEnvelope
from storage.ticket_repository import TicketRepository
from workflows.case_collab_workflow import CaseCollabWorkflow
from workflows.support_intake_workflow import SupportIntakeWorkflow


def test_ticket_to_collab_update_chain(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "trace.log"

    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    ticket_api = TicketAPI(repo)
    logger = JsonTraceLogger(log_path)

    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    tool_router = ToolRouter(ticket_api=ticket_api, retriever=retriever, trace_logger=logger)
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
        trace_logger=logger,
    )

    collab = CaseCollabWorkflow(ticket_api)
    intake = SupportIntakeWorkflow(engine, case_collab_workflow=collab)

    intake_result = intake.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-w2",
            message_text="设备故障需要工程师处理",
            metadata={"thread_id": "thread-w2", "trace_id": "trace_w2_chain"},
        )
    )
    ticket_id = intake_result.ticket_id

    collab.handle_command(ticket_id=ticket_id, actor_id="agent-a", command_line="/claim")
    collab.handle_command(ticket_id=ticket_id, actor_id="agent-a", command_line="/reassign agent-b")

    final_action = collab.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-b",
        command_line="/close completed onsite fix",
    )

    assert final_action.ticket.status == "closed"
    events = ticket_api.list_events(ticket_id)
    event_types = [event.event_type for event in events]
    assert "collab_claim" in event_types
    assert "collab_reassign" in event_types
    assert "collab_close" in event_types
