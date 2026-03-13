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


def test_workflow_engine_processes_complaint_with_handoff(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
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

    engine = WorkflowEngine(
        ticket_api=ticket_api,
        intent_router=IntentRouter(),
        tool_router=tool_router,
        summary_engine=SummaryEngine(),
        handoff_manager=HandoffManager.from_file(policy_path),
        sla_engine=SlaEngine.from_file(policy_path),
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


def test_workflow_engine_consulting_first_reuses_existing_consulting_ticket(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    ticket_api = TicketAPI(repo)
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    trace_logger = JsonTraceLogger(tmp_path / "consulting_trace.log")
    tool_router = ToolRouter(ticket_api=ticket_api, retriever=retriever, trace_logger=trace_logger)
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
        trace_logger=trace_logger,
    )

    first = engine.process_intake(
        InboundEnvelope(
            channel="wecom",
            session_id="session-consulting-001",
            message_text="请问物业报修流程怎么走？",
            metadata={"thread_id": "thread-consulting-001", "trace_id": "trace_consulting_001"},
        )
    )
    second = engine.process_intake(
        InboundEnvelope(
            channel="wecom",
            session_id="session-consulting-001",
            message_text="你好，再问一下流程材料需要什么？",
            metadata={"thread_id": "thread-consulting-001", "trace_id": "trace_consulting_002"},
        )
    )

    assert first.ticket.queue == "faq"
    assert second.ticket.queue == "faq"
    assert second.ticket.ticket_id == first.ticket.ticket_id

    trace_events = trace_logger.query_by_trace("trace_consulting_002", limit=200)
    assert any(str(item.get("event_type")) == "consulting_ticket_reused" for item in trace_events)
