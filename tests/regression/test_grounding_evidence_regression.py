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


def test_grounding_evidence_is_attached_regression(tmp_path: Path) -> None:
    repo = TicketRepository(tmp_path / "tickets.db")
    repo.apply_migrations()
    ticket_api = TicketAPI(repo)
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    tool_router = ToolRouter(ticket_api=ticket_api, retriever=retriever)
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "seed_data"
        / "sla_rules"
        / "default_sla_rules.json"
    )
    workflow = WorkflowEngine(
        ticket_api=ticket_api,
        intent_router=IntentRouter(),
        tool_router=tool_router,
        summary_engine=SummaryEngine(),
        handoff_manager=HandoffManager.from_file(policy_path),
        sla_engine=SlaEngine.from_file(policy_path),
        recommendation_engine=RecommendedActionsEngine(),
    )

    outcome = workflow.process_intake(
        InboundEnvelope(
            channel="wecom",
            session_id="grounding-reg-1",
            message_text="支付重复扣费需要退款",
            metadata={"thread_id": "thread-grounding-reg-1"},
        )
    )

    assert outcome.retrieved_docs
    assert any(doc.source_type == "history_case" for doc in outcome.retrieved_docs)
    assert "参考证据：" in outcome.reply_text
    assert any("evidence=" in action.reason for action in outcome.recommendations)
