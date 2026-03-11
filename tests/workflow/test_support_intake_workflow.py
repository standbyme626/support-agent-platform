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
    assert result.ticket_action == "faq_reply"
    assert result.handoff_required is False
    assert "direct_reply" in result.trace_events


def test_support_intake_greeting_no_handoff_and_no_collab_push(tmp_path: Path) -> None:
    workflow, _ = _build_intake_workflow(tmp_path)
    result = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-greeting",
            message_text="你好",
            metadata={"thread_id": "thread-greeting"},
        )
    )

    assert result.handoff_required is False
    assert result.collab_push is None
    assert result.ticket_action == "greeting_reply"
    assert "你好" in result.reply_text
    assert "direct_reply" in result.trace_events


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
    assert result.ticket_action == "create_ticket"
    assert result.queue == "support"
    assert result.priority in {"P1", "P2", "P3", "P4"}
    assert result.recommended_actions
    assert "evidence" in result.recommended_actions[0]

    events = ticket_api.list_events(result.ticket_id)
    event_types = {event.event_type for event in events}
    assert "ticket_classified" in event_types
    assert "ticket_context_retrieved" in event_types
    assert "ticket_draft_generated" in event_types


def test_support_intake_handoff_event_contains_policy_paths(tmp_path: Path) -> None:
    workflow, ticket_api = _build_intake_workflow(tmp_path)
    result = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-complaint-handoff",
            message_text="我要投诉并要求人工客服马上处理",
            metadata={"thread_id": "thread-complaint-handoff"},
        )
    )

    assert result.handoff_required is True
    events = ticket_api.list_events(result.ticket_id)
    handoff_events = [item for item in events if item.event_type == "ticket_handoff_requested"]
    assert handoff_events

    payload = handoff_events[-1].payload
    assert str(payload["sla_rule_path"]).startswith("sla.")
    assert isinstance(payload["handoff_rule_paths"], list)
    assert payload["handoff_rule_paths"]
