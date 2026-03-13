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
from openclaw_adapter.session_mapper import SessionMapper
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


def _build_intake_workflow_with_session_mapper(
    tmp_path: Path,
) -> tuple[SupportIntakeWorkflow, TicketAPI, SessionMapper]:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    session_mapper = SessionMapper(tmp_path / "sessions.db")
    ticket_api = TicketAPI(repo, session_mapper=session_mapper)
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
        session_mapper,
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
    assert result.reply_text == f"已创建工单 {result.ticket_id}，状态：待认领。已通知处理同学。"
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


def test_support_intake_progress_query_updates_existing_ticket(tmp_path: Path) -> None:
    workflow, _ = _build_intake_workflow(tmp_path)
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-progress",
            message_text="停车场抬杆故障",
            metadata={"thread_id": "thread-progress"},
        )
    )
    second = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-progress",
            message_text="我的工单到哪了，谁在跟进？",
            metadata={"thread_id": "thread-progress"},
        ),
        existing_ticket_id=first.ticket_id,
    )

    assert second.ticket_id == first.ticket_id
    assert second.ticket_action == "progress_reply"
    assert "工单" in second.reply_text
    assert "负责人" in second.reply_text


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


def test_support_intake_progress_query_prefers_active_ticket_in_session_context(
    tmp_path: Path,
) -> None:
    workflow, _, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-multi-progress",
            message_text="停车场抬杆故障，需要报修",
            metadata={"thread_id": "thread-multi-progress"},
        )
    )
    session_mapper.begin_new_issue("session-multi-progress")
    second = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-multi-progress",
            message_text="电梯异响，另一个新问题",
            metadata={"thread_id": "thread-multi-progress"},
        )
    )

    assert second.ticket_id != first.ticket_id

    session_context = session_mapper.get_session_context("session-multi-progress")
    progress = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-multi-progress",
            message_text="这个问题现在进度到哪了？",
            metadata={
                "thread_id": "thread-multi-progress",
                "ticket_id": second.ticket_id,
                "active_ticket_id": second.ticket_id,
                "recent_ticket_ids": [first.ticket_id],
                "session_context": session_context,
            },
        ),
        existing_ticket_id=None,
    )

    assert progress.ticket_id == second.ticket_id
    assert progress.ticket_action == "progress_reply"


def test_support_intake_ambiguous_message_enters_clarification_without_forced_judgement(
    tmp_path: Path,
) -> None:
    workflow, ticket_api, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    session_id = "session-clarification-flow"
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="停车场抬杆故障，需要报修",
            metadata={"thread_id": "thread-clarification-flow"},
        )
    )
    session_mapper.begin_new_issue(session_id)
    second = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="电梯异响，另一个问题",
            metadata={"thread_id": "thread-clarification-flow"},
        )
    )
    assert second.ticket_id != first.ticket_id

    before_tickets = ticket_api.list_all_tickets(limit=100)
    session_context = session_mapper.get_session_context(session_id)
    ambiguous = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="帮我看看",
            metadata={
                "thread_id": "thread-clarification-flow",
                "ticket_id": second.ticket_id,
                "active_ticket_id": second.ticket_id,
                "recent_ticket_ids": [first.ticket_id],
                "session_context": session_context,
            },
        )
    )
    after_tickets = ticket_api.list_all_tickets(limit=100)

    assert len(after_tickets) == len(before_tickets)
    assert ambiguous.ticket_action == "clarification_required"
    assert ambiguous.ticket_id == second.ticket_id
    assert "确认你在跟进哪一个问题" in ambiguous.reply_text
    assert ambiguous.outcome.reply_generation_type == "disambiguation"
    assert ambiguous.reply_trace["prompt_key"] == "disambiguation_reply"
    context_after = session_mapper.get_session_context(session_id)
    assert context_after["session_mode"] == "awaiting_disambiguation"


def test_support_intake_awaiting_new_issue_mode_creates_new_ticket(
    tmp_path: Path,
) -> None:
    workflow, _, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    session_id = "session-new-issue-flow"
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="停车场抬杆故障，需要报修",
            metadata={"thread_id": "thread-new-issue-flow"},
        )
    )
    session_mapper.begin_new_issue(session_id)
    session_context = session_mapper.get_session_context(session_id)

    second = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="电梯突然异响，也需要报修",
            metadata={
                "thread_id": "thread-new-issue-flow",
                "recent_ticket_ids": [first.ticket_id],
                "session_context": session_context,
            },
        )
    )

    assert second.ticket_id != first.ticket_id
    context_after = session_mapper.get_session_context(session_id)
    assert context_after["active_ticket_id"] == second.ticket_id
    assert first.ticket_id in context_after["recent_ticket_ids"]
    assert context_after["session_mode"] == "new_issue_detected"


def test_support_intake_explicit_new_command_switches_mode_without_creating_ticket(
    tmp_path: Path,
) -> None:
    workflow, _, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    session_id = "session-command-new-priority"
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="停车场抬杆故障，需要报修",
            metadata={"thread_id": "thread-command-new-priority"},
        )
    )
    session_context = session_mapper.get_session_context(session_id)
    second = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="/new 继续当前问题",
            metadata={
                "thread_id": "thread-command-new-priority",
                "active_ticket_id": first.ticket_id,
                "recent_ticket_ids": [],
                "session_context": session_context,
            },
        )
    )

    assert second.ticket_id == first.ticket_id
    assert second.ticket_action == "new_issue_mode"
    assert second.reply_text == "已切换到新问题模式，请描述你的新问题。"
    context_after = session_mapper.get_session_context(session_id)
    assert context_after["active_ticket_id"] is None
    assert context_after["session_mode"] == "awaiting_new_issue"


def test_support_intake_end_phrase_resets_session_context_without_new_ticket(
    tmp_path: Path,
) -> None:
    workflow, ticket_api, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    session_id = "session-end-phrase-flow"
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="停车场抬杆故障，需要报修",
            metadata={"thread_id": "thread-end-phrase-flow"},
        )
    )
    session_mapper.begin_new_issue(session_id)
    second = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="电梯异响，另一个问题",
            metadata={"thread_id": "thread-end-phrase-flow"},
        )
    )
    assert second.ticket_id != first.ticket_id
    before_count = len(ticket_api.list_all_tickets(limit=100))
    session_context = session_mapper.get_session_context(session_id)

    ended = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="这轮先到这里，结束当前对话",
            metadata={
                "thread_id": "thread-end-phrase-flow",
                "active_ticket_id": second.ticket_id,
                "recent_ticket_ids": [first.ticket_id],
                "session_context": session_context,
            },
        )
    )
    after_count = len(ticket_api.list_all_tickets(limit=100))

    assert after_count == before_count
    assert ended.ticket_action == "session_end"
    assert ended.reply_trace["session_action"] == "session_end"
    assert "session_end" in ended.trace_events
    context_after = session_mapper.get_session_context(session_id)
    assert context_after["active_ticket_id"] is None
    assert context_after["session_mode"] == "awaiting_new_issue"


def test_support_intake_message_after_session_end_creates_new_context_reply(
    tmp_path: Path,
) -> None:
    workflow, _, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    session_id = "session-after-end-new-context"
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="停车场抬杆故障，需要报修",
            metadata={"thread_id": "thread-after-end-new-context"},
        )
    )
    ended = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="这轮先到这里，结束当前对话",
            metadata={
                "thread_id": "thread-after-end-new-context",
                "ticket_id": first.ticket_id,
                "active_ticket_id": first.ticket_id,
                "session_context": session_mapper.get_session_context(session_id),
            },
        )
    )
    assert ended.ticket_action == "session_end"
    next_issue = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="打印机现在又报错了。",
            metadata={
                "thread_id": "thread-after-end-new-context",
                "session_context": session_mapper.get_session_context(session_id),
            },
        )
    )
    assert next_issue.ticket_id != first.ticket_id
    assert next_issue.reply_text == "已按新会话处理，并创建/关联新工单上下文。"


def test_support_intake_explicit_ticket_reference_uses_switch_reply_type(
    tmp_path: Path,
) -> None:
    workflow, ticket_api, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    session_id = "session-switch-reply-flow"
    first = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="停车场抬杆故障，需要报修",
            metadata={"thread_id": "thread-switch-reply-flow"},
        )
    )
    session_mapper.begin_new_issue(session_id)
    second = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text="电梯异响，另一个问题",
            metadata={"thread_id": "thread-switch-reply-flow"},
        )
    )
    assert second.ticket_id != first.ticket_id

    session_context = session_mapper.get_session_context(session_id)
    switched = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id=session_id,
            message_text=f"请切换到工单 {first.ticket_id} 继续处理",
            metadata={
                "thread_id": "thread-switch-reply-flow",
                "ticket_id": second.ticket_id,
                "active_ticket_id": second.ticket_id,
                "recent_ticket_ids": [first.ticket_id],
                "session_context": session_context,
            },
        ),
        existing_ticket_id=None,
    )

    assert switched.ticket_id == first.ticket_id
    assert switched.outcome.reply_generation_type == "switch"
    assert switched.reply_trace["prompt_key"] == "switch_reply"
    after_context = ticket_api.get_session_context(session_id) or {}
    assert after_context.get("active_ticket_id") == first.ticket_id


def test_support_intake_collab_commands_execute_with_ticket_id_argument(
    tmp_path: Path,
) -> None:
    workflow, ticket_api, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    seed = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-collab-command-flow",
            message_text="空调不制冷，办公室 3A，今天一直有异响。",
            metadata={"thread_id": "thread-collab-command-flow"},
        )
    )
    session_context = session_mapper.get_session_context("session-collab-command-flow")

    claimed = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-collab-command-flow",
            message_text=f"/claim {seed.ticket_id}",
            metadata={
                "thread_id": "thread-collab-command-flow",
                "ticket_id": seed.ticket_id,
                "active_ticket_id": seed.ticket_id,
                "session_context": session_context,
            },
        )
    )
    assert claimed.ticket_action == "collab_claim"
    assert claimed.reply_text.startswith("认领成功：")

    resolved = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-collab-command-flow",
            message_text=f"/resolve {seed.ticket_id} 远程重启后已恢复",
            metadata={
                "thread_id": "thread-collab-command-flow",
                "ticket_id": seed.ticket_id,
                "active_ticket_id": seed.ticket_id,
                "session_context": session_context,
            },
        )
    )
    assert resolved.ticket_action == "collab_resolve"
    assert resolved.reply_text == f"工单 {seed.ticket_id} 已处理完成，请确认是否恢复正常。"
    ticket_after_resolve = ticket_api.require_ticket(seed.ticket_id)
    assert ticket_after_resolve.status == "resolved"
    assert ticket_after_resolve.handoff_state == "waiting_customer"

    confirmed = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-collab-command-flow",
            message_text=f"/customer-confirm {seed.ticket_id} 已经恢复了，可以结单",
            metadata={
                "thread_id": "thread-collab-command-flow",
                "ticket_id": seed.ticket_id,
                "active_ticket_id": seed.ticket_id,
                "session_context": session_context,
            },
        )
    )
    assert confirmed.ticket_action == "collab_customer_confirm"
    assert confirmed.reply_text == f"收到确认，工单 {seed.ticket_id} 已关闭。"
    ticket_after_close = ticket_api.require_ticket(seed.ticket_id)
    assert ticket_after_close.status == "closed"
    assert ticket_after_close.close_reason == "customer_confirmed"


def test_support_intake_customer_confirmation_phrase_closes_resolved_ticket(
    tmp_path: Path,
) -> None:
    workflow, ticket_api, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    seed = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-customer-confirm-phrase",
            message_text="空调不制冷，办公室 3A，今天一直有异响。",
            metadata={"thread_id": "thread-customer-confirm-phrase"},
        )
    )
    session_context = session_mapper.get_session_context("session-customer-confirm-phrase")
    workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-customer-confirm-phrase",
            message_text=f"/resolve {seed.ticket_id} 远程重启后已恢复",
            metadata={
                "thread_id": "thread-customer-confirm-phrase",
                "ticket_id": seed.ticket_id,
                "active_ticket_id": seed.ticket_id,
                "session_context": session_context,
            },
        )
    )

    confirmed = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-customer-confirm-phrase",
            message_text="已经恢复了，可以结单。",
            metadata={
                "thread_id": "thread-customer-confirm-phrase",
                "ticket_id": seed.ticket_id,
                "active_ticket_id": seed.ticket_id,
                "session_context": session_context,
            },
        )
    )
    assert confirmed.ticket_action == "collab_customer_confirm"
    assert confirmed.reply_text == f"收到确认，工单 {seed.ticket_id} 已关闭。"
    closed_ticket = ticket_api.require_ticket(seed.ticket_id)
    assert closed_ticket.status == "closed"
    assert closed_ticket.close_reason == "customer_confirmed"


def test_support_intake_operator_close_and_advice_only_terminal_phrase(
    tmp_path: Path,
) -> None:
    workflow, ticket_api, session_mapper = _build_intake_workflow_with_session_mapper(tmp_path)
    seed = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-operator-close-flow",
            message_text="停车场道闸故障，无法落杆。",
            metadata={"thread_id": "thread-operator-close-flow"},
        )
    )
    session_context = session_mapper.get_session_context("session-operator-close-flow")
    closed = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-operator-close-flow",
            message_text=f"/operator-close {seed.ticket_id} 用户离线，电话确认恢复",
            metadata={
                "thread_id": "thread-operator-close-flow",
                "ticket_id": seed.ticket_id,
                "active_ticket_id": seed.ticket_id,
                "session_context": session_context,
            },
        )
    )
    assert closed.ticket_action == "collab_operator_close"
    assert closed.reply_text == f"已强制关闭 {seed.ticket_id}，原因已记录。"
    closed_ticket = ticket_api.require_ticket(seed.ticket_id)
    assert closed_ticket.status == "closed"
    assert closed_ticket.close_reason == "operator_forced_close"

    another = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-operator-advice-flow",
            message_text="会议室投屏连不上。",
            metadata={"thread_id": "thread-operator-advice-flow"},
        )
    )
    advice_context = session_mapper.get_session_context("session-operator-advice-flow")
    advised = workflow.run(
        InboundEnvelope(
            channel="wecom",
            session_id="session-operator-advice-flow",
            message_text="请帮我结束这个工单。",
            metadata={
                "thread_id": "thread-operator-advice-flow",
                "ticket_id": another.ticket_id,
                "active_ticket_id": another.ticket_id,
                "session_context": advice_context,
            },
        )
    )
    assert advised.ticket_action == "advice_only"
    assert advised.reply_text == (
        f"建议执行：/resolve {another.ticket_id} 或 /operator-close {another.ticket_id} 原因。"
    )
    untouched_ticket = ticket_api.require_ticket(another.ticket_id)
    assert untouched_ticket.status != "closed"
