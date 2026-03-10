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


def test_workflow_r_to_s_chain(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    api = TicketAPI(repo)
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    tool_router = ToolRouter(ticket_api=api, retriever=retriever)

    workflow_engine = WorkflowEngine(
        ticket_api=api,
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

    case_workflow = CaseCollabWorkflow(api)
    intake_workflow = SupportIntakeWorkflow(
        workflow_engine,
        case_collab_workflow=case_workflow,
    )

    intake_result = intake_workflow.run(
        InboundEnvelope(
            channel="telegram",
            session_id="session-rs",
            message_text="设备故障需要尽快处理",
            metadata={"thread_id": "thread-rs"},
        )
    )
    assert intake_result.collab_push is not None

    ticket_id = intake_result.ticket_id
    case_workflow.handle_command(ticket_id=ticket_id, actor_id="agent-1", command_line="/claim")
    case_workflow.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-1",
        command_line="/escalate supplier dependency",
    )
    closed = case_workflow.handle_command(
        ticket_id=ticket_id,
        actor_id="agent-1",
        command_line="/close replaced broken part",
    )

    assert closed.ticket.status == "closed"
