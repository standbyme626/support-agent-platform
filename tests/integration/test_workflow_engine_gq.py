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


def test_workflow_engine_processes_complaint_with_handoff(tmp_path: Path) -> None:
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

    outcome = engine.process_intake(
        InboundEnvelope(
            channel="telegram",
            session_id="session-9",
            message_text="我要投诉，必须人工客服现在处理",
            metadata={"thread_id": "thread-9"},
        )
    )

    assert outcome.ticket.ticket_id.startswith("TCK-")
    assert outcome.handoff.should_handoff is True
    assert outcome.ticket.status == "handoff"
    assert "人工" in outcome.reply_text
