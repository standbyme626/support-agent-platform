from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


def _build_workflow(tmp_path: Path) -> tuple[WorkflowEngine, TicketAPI, SlaEngine, JsonTraceLogger]:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "trace.log"

    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    ticket_api = TicketAPI(repo)

    logger = JsonTraceLogger(log_path)
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    sla_engine = SlaEngine.from_file(
        Path(__file__).resolve().parents[2] / "seed_data" / "sla_rules" / "default_sla_rules.json"
    )
    tool_router = ToolRouter(ticket_api=ticket_api, retriever=retriever, trace_logger=logger)
    workflow = WorkflowEngine(
        ticket_api=ticket_api,
        intent_router=IntentRouter(),
        tool_router=tool_router,
        summary_engine=SummaryEngine(),
        handoff_manager=HandoffManager(),
        sla_engine=sla_engine,
        recommendation_engine=RecommendedActionsEngine(),
        trace_logger=logger,
    )
    return workflow, ticket_api, sla_engine, logger


def test_faq_response_regression(tmp_path: Path) -> None:
    workflow, _, _, _ = _build_workflow(tmp_path)
    outcome = workflow.process_intake(
        InboundEnvelope(
            channel="telegram",
            session_id="faq-reg",
            message_text="如何 查询 工单 进度",
            metadata={"thread_id": "thread-faq", "trace_id": "trace_reg_faq"},
        )
    )

    assert "工单查询" in outcome.reply_text
    assert outcome.handoff.should_handoff is False


def test_handoff_regression(tmp_path: Path) -> None:
    workflow, _, _, logger = _build_workflow(tmp_path)
    outcome = workflow.process_intake(
        InboundEnvelope(
            channel="wecom",
            session_id="handoff-reg",
            message_text="我要投诉并要求人工客服现在处理",
            metadata={"thread_id": "thread-handoff", "trace_id": "trace_reg_handoff"},
        )
    )

    assert outcome.handoff.should_handoff is True
    assert outcome.ticket.status == "handoff"

    trace_events = logger.query_by_trace("trace_reg_handoff")
    event_types = {event["event_type"] for event in trace_events}
    assert "handoff_decision" in event_types


def test_sla_trigger_regression(tmp_path: Path) -> None:
    workflow, ticket_api, sla_engine, logger = _build_workflow(tmp_path)
    outcome = workflow.process_intake(
        InboundEnvelope(
            channel="telegram",
            session_id="sla-reg",
            message_text="支付扣费异常",
            metadata={"thread_id": "thread-sla", "trace_id": "trace_reg_sla"},
        )
    )

    ticket = ticket_api.require_ticket(outcome.ticket.ticket_id)
    events = ticket_api.list_events(ticket.ticket_id)
    evaluated = sla_engine.evaluate(ticket, events, now=datetime.now(UTC) + timedelta(hours=6))

    assert "resolution_overdue" in evaluated.breached_items
    trace_events = logger.query_by_trace("trace_reg_sla")
    assert any(event["event_type"] == "sla_evaluated" for event in trace_events)
