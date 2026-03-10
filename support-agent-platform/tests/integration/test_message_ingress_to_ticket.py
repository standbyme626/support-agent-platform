from __future__ import annotations

from pathlib import Path

from channel_adapters.feishu_adapter import FeishuAdapter
from channel_adapters.telegram_adapter import TelegramAdapter
from channel_adapters.wecom_adapter import WeComAdapter
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
from openclaw_adapter.bindings import GatewayBindings
from openclaw_adapter.channel_router import ChannelRouter
from openclaw_adapter.gateway import OpenClawGateway
from openclaw_adapter.session_mapper import SessionMapper
from storage.models import InboundEnvelope
from storage.ticket_repository import TicketRepository
from workflows.case_collab_workflow import CaseCollabWorkflow
from workflows.support_intake_workflow import SupportIntakeWorkflow


def test_message_ingress_to_ticket_creation(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "gateway.log"

    bindings = GatewayBindings(
        channel_router=ChannelRouter(
            {"feishu": FeishuAdapter(), "telegram": TelegramAdapter(), "wecom": WeComAdapter()}
        ),
        session_mapper=SessionMapper(sqlite_path),
        trace_logger=JsonTraceLogger(log_path),
    )
    gateway = OpenClawGateway(bindings)

    ingress = gateway.receive(
        "telegram",
        {
            "trace_id": "trace_w1_ingress",
            "message": {"chat": {"id": 67890, "username": "qa"}, "text": "设备故障报修"},
        },
    )

    inbound_raw = ingress["inbound"]
    envelope = InboundEnvelope(
        channel=str(inbound_raw["channel"]),
        session_id=str(inbound_raw["session_id"]),
        message_text=str(inbound_raw["message_text"]),
        metadata=dict(inbound_raw["metadata"]),
    )

    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    ticket_api = TicketAPI(repo, session_mapper=bindings.session_mapper)
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    tool_router = ToolRouter(
        ticket_api=ticket_api, retriever=retriever, trace_logger=bindings.trace_logger
    )

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
        trace_logger=bindings.trace_logger,
    )

    workflow = SupportIntakeWorkflow(engine, case_collab_workflow=CaseCollabWorkflow(ticket_api))
    result = workflow.run(envelope)

    assert result.ticket_id.startswith("TCK-")
    bound = bindings.session_mapper.get("67890")
    assert bound is not None
    assert bound.ticket_id == result.ticket_id
