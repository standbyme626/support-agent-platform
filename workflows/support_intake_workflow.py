from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from core.disambiguation import DisambiguationResult
from core.handoff_manager import HandoffDecision
from core.hitl.handoff_context import HANDOFF_CONTEXT_KEY, build_handoff_context
from core.retrieval.source_attribution import build_source_payloads
from core.sla_engine import SlaCheckResult
from core.summary_engine import build_handoff_summary
from core.ticket_api import TicketAPI
from core.workflow_engine import WorkflowEngine, WorkflowOutcome
from runtime.graph.intake_graph import SupportIntakeGraphRunner
from storage.models import InboundEnvelope, Ticket, TicketEvent

from .case_collab_workflow import CaseCollabWorkflow


@dataclass(frozen=True)
class SupportIntakeResult:
    ticket_id: str | None
    reply_text: str
    handoff: bool
    collab_push: dict[str, str] | None
    outcome: WorkflowOutcome | None
    ticket_action: str
    summary: str | None
    recommended_actions: list[dict[str, object]]
    handoff_required: bool
    queue: str
    priority: str
    trace_events: list[str]
    llm_trace: dict[str, object] | None
    reply_trace: dict[str, object]


class SupportIntakeWorkflow:
    """Workflow A: intake entry -> FAQ reply -> auto-ticket -> handoff.

    Business routing/transition rules are enforced here (workflow/core),
    not inside the OpenClaw ingress/session/routing adapter layer.
    """

    _COLLAB_COMMAND_RE = re.compile(r"^\s*/\s*(?P<command>[a-zA-Z][\w-]*)(?:\s+(?P<rest>.*))?\s*$")
    _TICKET_ID_RE = re.compile(r"^(?:TCK-[A-Za-z0-9_-]+|TICKET-[A-Za-z0-9_-]+)$")
    _TICKET_ID_SEARCH_RE = re.compile(
        r"\b(?:TCK-[A-Za-z0-9_-]+|TICKET-[A-Za-z0-9_-]+)\b", re.IGNORECASE
    )
    _COLLAB_COMMAND_ALIASES = {
        "claim": "claim",
        "take": "claim",
        "pickup": "claim",
        "resolve": "resolve",
        "customer-confirm": "customer-confirm",
        "customerconfirm": "customer-confirm",
        "confirm": "customer-confirm",
        "operator-close": "operator-close",
        "operatorclose": "operator-close",
        "op-close": "operator-close",
        "force-close": "operator-close",
        "forceclose": "operator-close",
        "end-session": "end-session",
        "endsession": "end-session",
        "close": "close",
        "reopen": "reopen",
        "merge": "merge",
        "link": "link",
        "priority": "priority",
        "status": "status",
        "needs-info": "needs-info",
        "escalate": "escalate",
        "assign": "assign",
        "list": "list",
    }
    _COLLAB_NATURAL_KEYWORDS = {
        "claim": (
            "认领工单",
            "认领",
            "接手工单",
            "接手处理",
            "我来接手",
            "我来处理",
            "由我处理",
            "接单",
            "接单处理",
        ),
        "resolve": (
            "处理完成",
            "已处理完成",
            "已经处理完成",
            "已解决",
            "问题已解决",
            "处理好了",
            "修复完成",
            "已修复",
            "搞定了",
            "完成了",
            "解决了",
            "已经好了",
        ),
        "operator-close": (
            "强制关闭",
            "人工关闭",
            "操作关闭",
            "我来关闭",
            "由我关闭",
            "强制结单",
            "人工结单",
        ),
        "customer-confirm": (
            "确认解决",
            "确认已解决",
            "确认恢复",
            "确认修好",
            "确认处理好",
            "已确认",
            "确认",
            "好的",
            "可以了",
        ),
        "reopen": (
            "重新打开",
            "重开工单",
            "重新开启",
            "再开一下",
            "开启工单",
            "打开工单",
        ),
        "merge": (
            "合并工单",
            "合并到这个",
            "并入",
            "合并",
            "工单合并",
        ),
        "link": (
            "关联工单",
            "关联到",
            "关联",
            "工单关联",
            "关联这个",
        ),
        "list": (
            "查看工单列表",
            "查看所有工单",
            "查看我的工单列表",
            "我的工单列表",
            "工单列表",
            "有哪些工单",
            "查看P1工单",
            "查看P2工单",
            "查看P3工单",
            "查看P4工单",
            "查看紧急工单",
            "查看高优先级工单",
            "查看低优先级工单",
            "查看加急工单",
            "查看重要工单",
            "待处理工单列表",
            "处理中工单列表",
            "已完结工单列表",
            "我的工单",
            "查看工单",
        ),
        "priority": (
            "紧急",
            "加急",
            "高优先级",
            "紧急处理",
            "优先处理",
            "重要",
            "重要紧急",
            "急",
            "设置优先级",
            "优先级",
            "调高优先级",
            "调低优先级",
            "提升优先级",
            "降低优先级",
            "设置优先",
        ),
        "priority_p1": (
            "紧急",
            "十万火急",
            "非常紧急",
            "立即处理",
            "马上处理",
            "重要紧急",
            "急",
            "很急",
            "非常急",
        ),
        "priority_p2": (
            "加急",
            "高优先级",
            "优先处理",
            "紧急处理",
            "尽快处理",
            "重要",
            "比较急",
        ),
        "status": (
            "工单状态",
            "进度如何",
            "处理到哪",
            "现在什么状态",
            "查看状态",
            "查看进度",
            "状态查询",
            "工单进度",
            "处理进度",
            "现在怎样了",
        ),
        "needs-info": (
            "需要更多信息",
            "请补充信息",
            "缺少信息",
            "信息不足",
            "需要信息",
            "请补充",
            "补充信息",
            "请提供",
            "需要提供",
            "请告诉",
        ),
        "escalate": (
            "升级",
            "上报",
            "升级处理",
            "转上级",
            "上报处理",
            "转主管",
            "转经理",
        ),
        "assign": (
            "转给",
            "分配给",
            "指派给",
            "分配",
            "转交",
            "派给",
            "安排给",
        ),
        "merge": (
            "合并工单",
            "合并到这个",
            "并入",
            "合并",
        ),
    }
    _COLLAB_DEFAULT_NOTES = {
        "resolve": "处理人员确认问题已处理完成。",
        "operator-close": "处理人员执行关闭，原因已记录。",
        "reopen": "处理人员重新打开工单。",
        "merge": "工单已合并。",
        "link": "工单已关联。",
        "priority": "工单优先级已调整。",
        "escalate": "工单已升级处理。",
        "assign": "工单已转派。",
    }
    _TERMINAL_ADVICE_HINTS = (
        "请帮我结束这个工单",
        "请帮我关闭这个工单",
        "结束这个工单",
        "关闭这个工单",
        "结束工单",
        "关闭工单",
    )
    _CUSTOMER_CONFIRM_HINTS = (
        "已经恢复",
        "已恢复",
        "恢复了",
        "可以结单",
        "可以关闭",
        "确认恢复",
    )

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        *,
        case_collab_workflow: CaseCollabWorkflow | None = None,
        ticket_api: TicketAPI | None = None,
        intent_confidence_threshold: float = 0.58,
        faq_score_threshold: float = 0.20,
        handoff_confidence_threshold: float = 0.45,
        use_graph_runtime: bool = True,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._case_collab_workflow = case_collab_workflow
        self._ticket_api = ticket_api or getattr(case_collab_workflow, "_ticket_api", None)
        self._intent_confidence_threshold = intent_confidence_threshold
        self._faq_score_threshold = faq_score_threshold
        self._handoff_confidence_threshold = handoff_confidence_threshold
        self._graph_runner = SupportIntakeGraphRunner(self) if use_graph_runtime else None

    def run(
        self,
        envelope: InboundEnvelope,
        *,
        existing_ticket_id: str | None = None,
    ) -> SupportIntakeResult:
        if self._graph_runner is None:
            return self._run_without_graph(
                envelope=envelope,
                existing_ticket_id=existing_ticket_id,
            )
        return self._graph_runner.run(
            envelope=envelope,
            existing_ticket_id=existing_ticket_id,
        )

    def assess_disambiguation(
        self,
        envelope: InboundEnvelope,
        *,
        requested_ticket_id: str | None = None,
    ) -> DisambiguationResult:
        return self._workflow_engine.assess_disambiguation(
            envelope,
            requested_ticket_id=requested_ticket_id,
        )

    def run_standard_intake(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
        existing_ticket_id: str | None,
    ) -> SupportIntakeResult:
        return self._run_standard_intake(
            envelope=envelope,
            disambiguation=disambiguation,
            existing_ticket_id=existing_ticket_id,
        )

    def _run_without_graph(
        self,
        *,
        envelope: InboundEnvelope,
        existing_ticket_id: str | None,
    ) -> SupportIntakeResult:
        disambiguation = self.assess_disambiguation(
            envelope,
            requested_ticket_id=None,
        )
        envelope_with_disambiguation = self._tag_disambiguation_context(
            envelope,
            disambiguation=disambiguation,
        )
        session_end_result = self._build_session_end_result(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
        )
        if session_end_result is not None:
            return session_end_result
        session_new_result = self._build_session_new_issue_result(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
        )
        if session_new_result is not None:
            return session_new_result
        session_list_result = self._build_session_list_tickets_result(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
        )
        if session_list_result is not None:
            return session_list_result
        collab_command_result = self._build_collab_command_result(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
            existing_ticket_id=existing_ticket_id,
        )
        if collab_command_result is not None:
            return collab_command_result
        customer_confirmation_result = self._build_customer_confirmation_result(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
            existing_ticket_id=existing_ticket_id,
        )
        if customer_confirmation_result is not None:
            return customer_confirmation_result
        collab_advice_result = self._build_collab_advice_only_result(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
            existing_ticket_id=existing_ticket_id,
        )
        if collab_advice_result is not None:
            return collab_advice_result
        clarification = self._build_clarification_result(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
        )
        if clarification is not None:
            return clarification
        return self._run_standard_intake(
            envelope=envelope_with_disambiguation,
            disambiguation=disambiguation,
            existing_ticket_id=existing_ticket_id,
        )

    def _run_standard_intake(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
        existing_ticket_id: str | None,
    ) -> SupportIntakeResult:
        resolved_existing_ticket_id = self._workflow_engine.resolve_existing_ticket_id(
            envelope,
            requested_ticket_id=existing_ticket_id,
        )
        envelope_for_processing = envelope
        if disambiguation.decision == "new_issue_detected":
            resolved_existing_ticket_id = None
            envelope_for_processing = self._tag_new_issue_context(
                envelope,
                disambiguation=disambiguation,
            )

        outcome = self._workflow_engine.process_intake(
            envelope_for_processing,
            existing_ticket_id=resolved_existing_ticket_id,
            force_new_ticket=(disambiguation.decision == "new_issue_detected"),
        )
        self._record_intake_trace(envelope_for_processing, outcome)

        collab_push: dict[str, str] | None = None
        if self._should_push_to_collab(outcome, outcome.resolved_existing_ticket_id):
            if self._case_collab_workflow is None:
                raise RuntimeError("CaseCollabWorkflow is required for collaboration push")
            collab_push = self._case_collab_workflow.push_new_ticket(outcome.ticket.ticket_id)

        reply_text = self._build_collab_reply_text(
            outcome=outcome,
            collab_push=collab_push,
            envelope=envelope,
            disambiguation=disambiguation,
        )
        return self._build_outcome_result(
            outcome=outcome,
            reply_text=reply_text,
            collab_push=collab_push,
        )

    def _build_collab_reply_text(
        self,
        *,
        outcome: WorkflowOutcome,
        collab_push: dict[str, str] | None,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
    ) -> str:
        reply_text = outcome.reply_text
        if collab_push is None:
            return reply_text
        session_mode = ""
        session_context = envelope.metadata.get("session_context")
        if isinstance(session_context, dict):
            session_mode = str(session_context.get("session_mode") or "").strip()
        if session_mode == "awaiting_new_issue":
            return "已按新会话处理，并创建/关联新工单上下文。"
        if (
            disambiguation.decision == "new_issue_detected"
            and disambiguation.reason == "session_mode_awaiting_new_issue"
        ):
            return "已按新会话处理，并创建/关联新工单上下文。"
        if disambiguation.decision == "new_issue_detected":
            return "已开启新问题处理流程，正在为你生成新的工单记录。"
        if outcome.handoff.should_handoff:
            return reply_text
        return f"已创建工单 {outcome.ticket.ticket_id}，状态：待认领。已通知处理人员。"

    def _build_outcome_result(
        self,
        *,
        outcome: WorkflowOutcome,
        reply_text: str,
        collab_push: dict[str, str] | None,
    ) -> SupportIntakeResult:
        ticket_action, trace_events = self._derive_ticket_action(outcome)
        recommended_actions = [item.as_dict() for item in outcome.recommendations]
        return SupportIntakeResult(
            ticket_id=outcome.ticket.ticket_id,
            reply_text=reply_text,
            handoff=outcome.handoff.should_handoff,
            collab_push=collab_push,
            outcome=outcome,
            ticket_action=ticket_action,
            summary=outcome.summary,
            recommended_actions=recommended_actions,
            handoff_required=outcome.handoff.should_handoff,
            queue=outcome.ticket.queue,
            priority=outcome.ticket.priority,
            trace_events=trace_events,
            llm_trace=outcome.llm_trace,
            reply_trace=outcome.reply_trace,
        )

    @staticmethod
    def _attach_runtime_graph_trace(
        result: SupportIntakeResult,
        *,
        runtime_graph: str,
        runtime_current_node: str,
        runtime_path: list[str],
        runtime_state: dict[str, object],
    ) -> SupportIntakeResult:
        reply_trace = dict(result.reply_trace)
        reply_trace["runtime_graph"] = runtime_graph
        reply_trace["runtime_current_node"] = runtime_current_node
        reply_trace["runtime_path"] = list(runtime_path)
        reply_trace["runtime_state"] = dict(runtime_state)
        trace_events = list(result.trace_events)
        for node in runtime_path:
            if node not in trace_events:
                trace_events.append(node)
        return replace(
            result,
            reply_trace=reply_trace,
            trace_events=trace_events,
        )

    def _build_session_new_issue_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
    ) -> SupportIntakeResult | None:
        if disambiguation.session_action != "new_issue":
            return None
        if disambiguation.reason != "explicit_new_command":
            return None
        if self._ticket_api is None:
            return None

        message_text = str(envelope.message_text or "").strip()
        command_pattern = re.compile(r"^\s*/\s*new\s*$", re.IGNORECASE)
        is_only_command = command_pattern.match(message_text) is not None

        if not is_only_command:
            return None

        active_ticket_id = self._resolve_active_ticket_id(
            envelope=envelope,
            disambiguation=disambiguation,
            requested_ticket_id=None,
        )
        if active_ticket_id is not None:
            ticket = self._ticket_api.get_ticket(active_ticket_id)
        else:
            ticket = None

        self._ticket_api.reset_session_context(
            envelope.session_id,
            metadata={
                "session_mode": "awaiting_new_issue",
                "last_intent": "new_issue_requested",
                "disambiguation_reason": disambiguation.reason,
            },
        )

        if ticket is None:
            reply_text = "已切换到新问题模式，请描述你的新问题。"
            reply_trace = {
                "provider": "fallback",
                "prompt_key": "session_new_issue_reply",
                "prompt_version": "v1",
                "generation_type": "session_control",
                "fallback_used": True,
                "degraded": False,
                "degrade_reason": None,
                "decision": disambiguation.decision,
                "session_action": "new_issue",
                "reason": disambiguation.reason,
            }
            return SupportIntakeResult(
                ticket_id=None,
                reply_text=reply_text,
                handoff=False,
                collab_push=None,
                outcome=None,
                ticket_action="new_issue_mode",
                summary=None,
                recommended_actions=[],
                handoff_required=False,
                queue="",
                priority="",
                trace_events=["new_issue_mode", "session_context_reset"],
                llm_trace=None,
                reply_trace=reply_trace,
            )

        self._ticket_api.add_event(
            ticket.ticket_id,
            event_type="session_new_issue_requested",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "session_id": envelope.session_id,
                "reason": disambiguation.reason,
                "source": "user_input",
            },
        )

        refreshed_ticket = self._ticket_api.require_ticket(ticket.ticket_id)
        events = self._ticket_api.list_events(refreshed_ticket.ticket_id)
        sla_result = self._build_clarification_sla(refreshed_ticket, events)
        reply_text = "已切换到新问题模式，请描述你的新问题。"
        reply_trace = {
            "provider": "fallback",
            "prompt_key": "session_new_issue_reply",
            "prompt_version": "v1",
            "generation_type": "session_control",
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
            "decision": disambiguation.decision,
            "session_action": "new_issue",
            "reason": disambiguation.reason,
            "confidence": disambiguation.confidence,
        }
        llm_trace: dict[str, object] = {
            "provider": "fallback",
            "model": None,
            "prompt_key": "session_new_issue_reply",
            "prompt_version": "v1",
            "success": True,
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
        }
        outcome = WorkflowOutcome(
            ticket=refreshed_ticket,
            intent=disambiguation.intent,
            resolved_existing_ticket_id=refreshed_ticket.ticket_id,
            retrieved_docs=[],
            summary="用户请求切换到新问题模式，系统等待新的问题描述。",
            llm_trace=llm_trace,
            recommendations=[],
            handoff=HandoffDecision(
                should_handoff=False,
                reason="new_issue_mode_requested",
                payload={},
            ),
            sla=sla_result,
            reply_text=reply_text,
            reply_trace=reply_trace,
            reply_generation_type="session_control",
        )
        return SupportIntakeResult(
            ticket_id=refreshed_ticket.ticket_id,
            reply_text=reply_text,
            handoff=False,
            collab_push=None,
            outcome=outcome,
            ticket_action="new_issue_mode",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=refreshed_ticket.queue,
            priority=refreshed_ticket.priority,
            trace_events=["new_issue_mode", "session_context_reset"],
            llm_trace=llm_trace,
            reply_trace=reply_trace,
        )

    def _build_session_list_tickets_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
    ) -> SupportIntakeResult | None:
        if disambiguation.session_action != "list_tickets":
            return None
        if self._ticket_api is None or self._case_collab_workflow is None:
            return None

        parsed = self._parse_collab_command(envelope.message_text)
        if parsed is None:
            command_line = "/list"
        else:
            cmd, args, _ = parsed
            command_line = f"/{cmd} {' '.join(args)}" if args else f"/{cmd}"

        try:
            action = self._case_collab_workflow.handle_command(
                ticket_id="DUMMY",
                actor_id=envelope.metadata.get("actor_id", "system"),
                command_line=command_line,
            )
        except Exception:
            return None

        ticket_list_text = action.message
        reply_text = f"工单列表：{ticket_list_text}。如需查看详情，请提供工单号。"

        reply_trace = {
            "provider": "fallback",
            "prompt_key": "list_tickets_reply",
            "generation_type": "session_control",
            "fallback_used": True,
            "session_action": "list_tickets",
            "reason": disambiguation.reason,
        }

        return SupportIntakeResult(
            ticket_id=None,
            reply_text=reply_text,
            handoff=False,
            collab_push=None,
            outcome=None,
            ticket_action="list_tickets",
            summary=None,
            recommended_actions=[],
            handoff_required=False,
            queue="",
            priority="",
            trace_events=["list_tickets"],
            llm_trace=None,
            reply_trace=reply_trace,
        )

    @staticmethod
    def _tag_disambiguation_context(
        envelope: InboundEnvelope,
        *,
        disambiguation: DisambiguationResult,
    ) -> InboundEnvelope:
        metadata = dict(envelope.metadata)
        metadata["disambiguation_decision"] = disambiguation.decision
        metadata["disambiguation_reason"] = disambiguation.reason
        metadata["disambiguation_confidence"] = round(disambiguation.confidence, 4)
        metadata["last_intent"] = disambiguation.intent.intent
        if disambiguation.session_action:
            metadata["session_control_action"] = disambiguation.session_action
            metadata["session_control_reason"] = disambiguation.reason
        if disambiguation.decision == "continue_current" and disambiguation.reason in {
            "explicit_ticket_in_message",
            "requested_ticket_id",
        }:
            metadata["reply_generation_hint"] = "switch"
        return replace(envelope, metadata=metadata)

    def _tag_new_issue_context(
        self,
        envelope: InboundEnvelope,
        *,
        disambiguation: DisambiguationResult,
    ) -> InboundEnvelope:
        metadata = dict(envelope.metadata)
        metadata["session_mode"] = "new_issue_detected"
        metadata["reply_generation_hint"] = "generic"
        if disambiguation.session_action:
            metadata["session_control_action"] = disambiguation.session_action
            metadata["session_control_reason"] = disambiguation.reason
        return replace(envelope, metadata=metadata)

    def _build_session_end_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
    ) -> SupportIntakeResult | None:
        if disambiguation.session_action != "session_end":
            return None
        if self._ticket_api is None:
            return None

        candidate_ticket_ids = list(disambiguation.candidate_ticket_ids)
        anchor_ticket_id = (
            disambiguation.active_ticket_id
            or disambiguation.suggested_ticket_id
            or (candidate_ticket_ids[0] if candidate_ticket_ids else None)
        )
        if anchor_ticket_id is None:
            return None
        ticket = self._ticket_api.get_ticket(anchor_ticket_id)
        if ticket is None:
            return None

        self._ticket_api.reset_session_context(
            envelope.session_id,
            metadata={
                "session_mode": "awaiting_new_issue",
                "last_intent": "session_end_requested",
                "disambiguation_reason": disambiguation.reason,
            },
        )
        self._ticket_api.add_event(
            ticket.ticket_id,
            event_type="session_end_requested",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "session_id": envelope.session_id,
                "reason": disambiguation.reason,
                "source": "user_input",
            },
        )

        refreshed_ticket = self._ticket_api.require_ticket(ticket.ticket_id)
        events = self._ticket_api.list_events(refreshed_ticket.ticket_id)
        sla_result = self._build_clarification_sla(refreshed_ticket, events)
        if disambiguation.reason == "explicit_end_command":
            reply_text = "当前会话已结束，可继续发起新问题。"
        else:
            reply_text = "好的，本次会话已结束。后续可随时发新问题。"
        reply_trace = {
            "provider": "fallback",
            "prompt_key": "session_end_reply",
            "prompt_version": "v1",
            "generation_type": "session_control",
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
            "decision": disambiguation.decision,
            "session_action": "session_end",
            "reason": disambiguation.reason,
            "confidence": disambiguation.confidence,
        }
        llm_trace: dict[str, object] = {
            "provider": "fallback",
            "model": None,
            "prompt_key": "session_end_reply",
            "prompt_version": "v1",
            "success": True,
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
        }
        outcome = WorkflowOutcome(
            ticket=refreshed_ticket,
            intent=disambiguation.intent,
            resolved_existing_ticket_id=refreshed_ticket.ticket_id,
            retrieved_docs=[],
            summary="用户请求结束当前会话，系统已重置会话上下文。",
            llm_trace=llm_trace,
            recommendations=[],
            handoff=HandoffDecision(
                should_handoff=False,
                reason="session_end_requested",
                payload={},
            ),
            sla=sla_result,
            reply_text=reply_text,
            reply_trace=reply_trace,
            reply_generation_type="session_control",
        )
        return SupportIntakeResult(
            ticket_id=refreshed_ticket.ticket_id,
            reply_text=reply_text,
            handoff=False,
            collab_push=None,
            outcome=outcome,
            ticket_action="session_end",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=refreshed_ticket.queue,
            priority=refreshed_ticket.priority,
            trace_events=["session_end", "session_context_reset"],
            llm_trace=llm_trace,
            reply_trace=reply_trace,
        )

    def _build_clarification_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
    ) -> SupportIntakeResult | None:
        if disambiguation.decision != "awaiting_disambiguation":
            return None
        if self._ticket_api is None:
            return None

        candidate_ticket_ids = list(disambiguation.candidate_ticket_ids)
        anchor_ticket_id = (
            disambiguation.suggested_ticket_id
            or disambiguation.active_ticket_id
            or (candidate_ticket_ids[0] if candidate_ticket_ids else None)
        )
        if anchor_ticket_id is None:
            return None
        ticket = self._ticket_api.get_ticket(anchor_ticket_id)
        if ticket is None:
            return None

        self._ticket_api.switch_active_session_ticket(
            envelope.session_id,
            ticket.ticket_id,
            metadata={
                "session_mode": "awaiting_disambiguation",
                "last_intent": disambiguation.intent.intent,
                "disambiguation_reason": disambiguation.reason,
            },
        )
        self._ticket_api.add_event(
            ticket.ticket_id,
            event_type="ticket_clarification_requested",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "reason": disambiguation.reason,
                "confidence": disambiguation.confidence,
                "candidate_ticket_ids": candidate_ticket_ids,
            },
        )

        refreshed_ticket = self._ticket_api.require_ticket(ticket.ticket_id)
        events = self._ticket_api.list_events(refreshed_ticket.ticket_id)
        sla_result = self._build_clarification_sla(refreshed_ticket, events)
        reply_text = self._build_clarification_reply(
            active_ticket_id=refreshed_ticket.ticket_id,
            candidate_ticket_ids=candidate_ticket_ids,
        )
        reply_trace = {
            "provider": "fallback",
            "prompt_key": "disambiguation_reply",
            "prompt_version": "v1",
            "generation_type": "disambiguation",
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
            "decision": disambiguation.decision,
            "reason": disambiguation.reason,
            "confidence": disambiguation.confidence,
            "candidate_ticket_ids": candidate_ticket_ids,
        }
        llm_trace: dict[str, object] = {
            "provider": "fallback",
            "model": None,
            "prompt_key": "disambiguation_reply",
            "prompt_version": "v1",
            "success": True,
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
        }
        outcome = WorkflowOutcome(
            ticket=refreshed_ticket,
            intent=disambiguation.intent,
            resolved_existing_ticket_id=refreshed_ticket.ticket_id,
            retrieved_docs=[],
            summary="进入澄清流程，等待用户确认继续当前问题或新建问题。",
            llm_trace=llm_trace,
            recommendations=[],
            handoff=HandoffDecision(
                should_handoff=False,
                reason="awaiting_disambiguation",
                payload={},
            ),
            sla=sla_result,
            reply_text=reply_text,
            reply_trace=reply_trace,
            reply_generation_type="disambiguation",
        )
        return SupportIntakeResult(
            ticket_id=refreshed_ticket.ticket_id,
            reply_text=reply_text,
            handoff=False,
            collab_push=None,
            outcome=outcome,
            ticket_action="clarification_required",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=refreshed_ticket.queue,
            priority=refreshed_ticket.priority,
            trace_events=["awaiting_disambiguation", "clarification_requested"],
            llm_trace=llm_trace,
            reply_trace=reply_trace,
        )

    def _build_clarification_sla(
        self,
        ticket: Ticket,
        events: list[TicketEvent],
    ) -> SlaCheckResult:
        _ = events
        created_at = ticket.created_at or datetime.now(UTC)
        return SlaCheckResult(
            first_response_due_at=ticket.first_response_due_at or created_at,
            resolution_due_at=ticket.resolution_due_at or created_at,
            breached_items=[],
            escalation_targets=[],
            policy_version="clarification_stub",
            matched_rule_id="clarification_stub",
            matched_rule_path="clarification_stub",
            used_fallback=True,
        )

    @staticmethod
    def _build_clarification_reply(
        *,
        active_ticket_id: str,
        candidate_ticket_ids: list[str],
    ) -> str:
        fallback_example = candidate_ticket_ids[0] if candidate_ticket_ids else active_ticket_id
        return (
            "我需要先确认你在跟进哪一个问题。"
            f"如果继续当前工单，请回复“继续当前”（{active_ticket_id}）；"
            "如果是新问题，请回复“新问题”；"
            f"也可以直接回复工单号（例如 {fallback_example}）。"
        )

    def _build_collab_command_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
        existing_ticket_id: str | None,
    ) -> SupportIntakeResult | None:
        if self._case_collab_workflow is None or self._ticket_api is None:
            return None

        parsed = self._parse_collab_command(envelope.message_text)
        if parsed is None:
            return None
        command, args, command_source = parsed

        active_ticket_id = self._resolve_active_ticket_id(
            envelope=envelope,
            disambiguation=disambiguation,
            requested_ticket_id=existing_ticket_id,
        )
        ticket_id = active_ticket_id
        command_args = list(args)
        if command_args and self._TICKET_ID_RE.match(command_args[0]):
            if command in {"merge", "link"}:
                pass
            else:
                ticket_id = command_args[0]
                command_args = command_args[1:]
        if ticket_id is None:
            return None

        actor_id = self._resolve_actor_id(envelope.metadata, session_id=envelope.session_id)
        command_line = f"/{command}"
        if command_args:
            command_line = f"{command_line} {' '.join(command_args)}"
        try:
            action = self._case_collab_workflow.handle_command(
                ticket_id=ticket_id,
                actor_id=actor_id,
                command_line=command_line,
            )
        except KeyError as error:
            return self._build_collab_command_error_result(
                envelope=envelope,
                disambiguation=disambiguation,
                command=command,
                command_source=command_source,
                requested_ticket_id=ticket_id,
                fallback_ticket_id=active_ticket_id,
                error=error,
            )
        except ValueError as error:
            error_message = str(error)
            if "requires" in error_message:
                return self._build_collab_usage_result(
                    envelope=envelope,
                    disambiguation=disambiguation,
                    command=command,
                    fallback_ticket_id=active_ticket_id or ticket_id,
                )
            return self._build_collab_command_error_result(
                envelope=envelope,
                disambiguation=disambiguation,
                command=command,
                command_source=command_source,
                requested_ticket_id=ticket_id,
                fallback_ticket_id=active_ticket_id,
                error=error,
            )

        ticket = self._ticket_api.require_ticket(ticket_id)
        events = self._ticket_api.list_events(ticket.ticket_id)
        sla_result = self._build_clarification_sla(ticket, events)
        resolved_command = action.command
        reply_text = self._render_collab_command_reply(
            command=resolved_command,
            ticket=ticket,
            actor_id=actor_id,
        )
        cross_group_sync = self._build_cross_group_sync_push(
            source_session_id=envelope.session_id,
            command=resolved_command,
            ticket=ticket,
            actor_id=actor_id,
        )
        trace_events = ["collab_command", resolved_command]
        if cross_group_sync is not None:
            trace_events.append("cross_group_sync")
        reply_trace = {
            "provider": "fallback",
            "prompt_key": "collab_command_reply",
            "prompt_version": "v1",
            "generation_type": "collab_command",
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
            "command": resolved_command,
            "ticket_id": ticket.ticket_id,
            "source": command_source,
            "cross_group_sync": cross_group_sync is not None,
        }
        if cross_group_sync is not None:
            reply_trace["cross_group_sync_target_session_id"] = cross_group_sync["session_id"]
        llm_trace: dict[str, object] = {
            "provider": "fallback",
            "model": None,
            "prompt_key": "collab_command_reply",
            "prompt_version": "v1",
            "success": True,
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
        }
        outcome = WorkflowOutcome(
            ticket=ticket,
            intent=disambiguation.intent,
            resolved_existing_ticket_id=ticket.ticket_id,
            retrieved_docs=[],
            summary=f"协同命令已执行：{resolved_command}",
            llm_trace=llm_trace,
            recommendations=[],
            handoff=HandoffDecision(
                should_handoff=False,
                reason="collab_command_executed",
                payload={"command": resolved_command},
            ),
            sla=sla_result,
            reply_text=reply_text,
            reply_trace=reply_trace,
            reply_generation_type="collab_command",
        )
        return SupportIntakeResult(
            ticket_id=ticket.ticket_id,
            reply_text=reply_text,
            handoff=False,
            collab_push=cross_group_sync,
            outcome=outcome,
            ticket_action=f"collab_{resolved_command.replace('-', '_')}",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=ticket.queue,
            priority=ticket.priority,
            trace_events=trace_events,
            llm_trace=llm_trace,
            reply_trace=reply_trace,
        )

    def _build_collab_advice_only_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
        existing_ticket_id: str | None,
    ) -> SupportIntakeResult | None:
        if self._ticket_api is None:
            return None
        text = str(envelope.message_text or "").strip()
        if not text or text.startswith("/"):
            return None
        if not any(hint in text for hint in self._TERMINAL_ADVICE_HINTS):
            return None

        ticket_id = self._resolve_active_ticket_id(
            envelope=envelope,
            disambiguation=disambiguation,
            requested_ticket_id=existing_ticket_id,
        )
        if ticket_id is None:
            return None
        ticket = self._ticket_api.get_ticket(ticket_id)
        if ticket is None:
            return None

        advice_reply = f"建议执行：/resolve {ticket_id} 或 /operator-close {ticket_id} 原因。"
        events = self._ticket_api.list_events(ticket_id)
        sla_result = self._build_clarification_sla(ticket, events)
        reply_trace = {
            "provider": "fallback",
            "prompt_key": "collab_advice_only_reply",
            "prompt_version": "v1",
            "generation_type": "advice_only",
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
            "advice_only": True,
            "ticket_id": ticket_id,
        }
        llm_trace: dict[str, object] = {
            "provider": "fallback",
            "model": None,
            "prompt_key": "collab_advice_only_reply",
            "prompt_version": "v1",
            "success": True,
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
        }
        outcome = WorkflowOutcome(
            ticket=ticket,
            intent=disambiguation.intent,
            resolved_existing_ticket_id=ticket_id,
            retrieved_docs=[],
            summary="用户请求终态动作，系统返回 advice-only 建议。",
            llm_trace=llm_trace,
            recommendations=[],
            handoff=HandoffDecision(
                should_handoff=False,
                reason="advice_only_terminal_guardrail",
                payload={"ticket_id": ticket_id},
            ),
            sla=sla_result,
            reply_text=advice_reply,
            reply_trace=reply_trace,
            reply_generation_type="advice_only",
        )
        return SupportIntakeResult(
            ticket_id=ticket_id,
            reply_text=advice_reply,
            handoff=False,
            collab_push=None,
            outcome=outcome,
            ticket_action="advice_only",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=ticket.queue,
            priority=ticket.priority,
            trace_events=["advice_only", "terminal_action_guardrail"],
            llm_trace=llm_trace,
            reply_trace=reply_trace,
        )

    def _build_customer_confirmation_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
        existing_ticket_id: str | None,
    ) -> SupportIntakeResult | None:
        if self._case_collab_workflow is None or self._ticket_api is None:
            return None
        text = str(envelope.message_text or "").strip()
        if not text or text.startswith("/"):
            return None
        if not any(hint in text for hint in self._CUSTOMER_CONFIRM_HINTS):
            return None

        ticket_id = self._resolve_active_ticket_id(
            envelope=envelope,
            disambiguation=disambiguation,
            requested_ticket_id=existing_ticket_id,
        )
        if ticket_id is None:
            return None
        ticket = self._ticket_api.get_ticket(ticket_id)
        if ticket is None:
            return None
        if ticket.status != "resolved" and ticket.handoff_state != "waiting_customer":
            return None

        synthetic_envelope = replace(
            envelope,
            message_text=f"/customer-confirm {ticket_id} {text}",
        )
        return self._build_collab_command_result(
            envelope=synthetic_envelope,
            disambiguation=disambiguation,
            existing_ticket_id=ticket_id,
        )

    def _build_collab_usage_result(
        self,
        *,
        envelope: InboundEnvelope | None,
        disambiguation: DisambiguationResult,
        command: str,
        fallback_ticket_id: str | None,
    ) -> SupportIntakeResult:
        if self._ticket_api is None:
            raise RuntimeError("Ticket API is required for collaboration command usage handling")
        ticket_id = (
            fallback_ticket_id
            or disambiguation.active_ticket_id
            or disambiguation.suggested_ticket_id
        )
        ticket = self._ticket_api.get_ticket(ticket_id) if ticket_id else None
        if ticket is None:
            effective_ticket_id = str(ticket_id or "TCK-UNKNOWN")
            if envelope is None:
                raise ValueError("ticket_id is required for collaboration command")
            ticket = Ticket(
                ticket_id=effective_ticket_id,
                channel=envelope.channel,
                session_id=envelope.session_id,
                thread_id=str(envelope.metadata.get("thread_id") or envelope.session_id),
                customer_id=None,
                title="协同命令格式提示",
                latest_message=str(envelope.message_text or ""),
                intent=disambiguation.intent.intent,
                priority="P3",
                status="open",
                queue="support",
                assignee=None,
                needs_handoff=False,
                metadata={"synthetic_ticket": True},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            ticket_id = effective_ticket_id
            events: list[TicketEvent] = []
        else:
            ticket_id = ticket.ticket_id
            events = self._ticket_api.list_events(ticket.ticket_id)
        sla_result = self._build_clarification_sla(ticket, events)
        usage_reply = (
            f"协同命令格式不正确：/{command}。"
            f"建议执行：/resolve {ticket_id} 或 /operator-close {ticket_id} 原因。"
        )
        reply_trace = {
            "provider": "fallback",
            "prompt_key": "collab_command_usage_reply",
            "prompt_version": "v1",
            "generation_type": "collab_command",
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
            "command": command,
            "ticket_id": ticket_id,
        }
        llm_trace: dict[str, object] = {
            "provider": "fallback",
            "model": None,
            "prompt_key": "collab_command_usage_reply",
            "prompt_version": "v1",
            "success": True,
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
        }
        outcome = WorkflowOutcome(
            ticket=ticket,
            intent=disambiguation.intent,
            resolved_existing_ticket_id=ticket_id,
            retrieved_docs=[],
            summary=f"协同命令格式错误：/{command}",
            llm_trace=llm_trace,
            recommendations=[],
            handoff=HandoffDecision(
                should_handoff=False,
                reason="collab_command_invalid",
                payload={"command": command},
            ),
            sla=sla_result,
            reply_text=usage_reply,
            reply_trace=reply_trace,
            reply_generation_type="collab_command",
        )
        return SupportIntakeResult(
            ticket_id=ticket_id,
            reply_text=usage_reply,
            handoff=False,
            collab_push=None,
            outcome=outcome,
            ticket_action="collab_command_invalid",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=ticket.queue,
            priority=ticket.priority,
            trace_events=["collab_command_invalid"],
            llm_trace=llm_trace,
            reply_trace=reply_trace,
        )

    @classmethod
    def _parse_collab_command(cls, message_text: str) -> tuple[str, list[str], str] | None:
        normalized_text = str(message_text or "").strip().replace("／", "/")
        if not normalized_text:
            return None
        match = cls._COLLAB_COMMAND_RE.match(normalized_text)
        if match is not None:
            raw_command = str(match.group("command") or "").strip()
            command = cls._canonicalize_collab_command(raw_command)
            if command is None:
                return None
            raw_rest = str(match.group("rest") or "").strip()
            args = raw_rest.split() if raw_rest else []
            return command, args, "slash_command"
        return cls._parse_natural_collab_command(normalized_text)

    @classmethod
    def _canonicalize_collab_command(cls, raw_command: str) -> str | None:
        normalized = str(raw_command or "").strip().lower().replace("_", "-")
        if not normalized:
            return None
        return cls._COLLAB_COMMAND_ALIASES.get(normalized)

    @classmethod
    def _parse_natural_collab_command(cls, text: str) -> tuple[str, list[str], str] | None:
        normalized = str(text or "").strip()
        if not normalized:
            return None

        lowered = normalized.lower()

        negative_patterns = (
            "不要",
            "不用",
            "别",
            "不需要",
            "不想",
            "能不能",
            "可以",
            "能帮我",
            "能否",
            "可不可以",
            "能不能够",
            "吗",
            "嘛",
            "呢",
            "?",
            "？",
        )
        question_patterns = (
            "能不能",
            "是否可以",
            "能否",
            "是不是",
            "有没有",
            "会不会",
            "可不可以",
            "能否",
            "请问",
            "问一下",
            "想知道",
        )
        request_help_patterns = (
            "帮我",
            "帮我一下",
            "请帮我",
            "麻烦",
            "能不能帮我",
            "能否帮我",
            "可以帮我",
            "帮我处理",
            "帮我看看",
        )

        if any(neg in lowered for neg in negative_patterns):
            return None
        if any(q in lowered for q in question_patterns):
            return None
        if any(p in lowered for p in request_help_patterns):
            return None

        if len(normalized) < 4:
            return None

        ticket_match = cls._TICKET_ID_SEARCH_RE.search(normalized)
        ticket_id = ticket_match.group(0).upper() if ticket_match is not None else None
        for command, keywords in cls._COLLAB_NATURAL_KEYWORDS.items():
            matched_keyword = next((item for item in keywords if item in normalized), None)
            if matched_keyword is None:
                continue
            if matched_keyword in {"我来处理", "由我处理"} and ticket_id is None:
                continue
            args: list[str] = []
            if ticket_id is not None:
                args.append(ticket_id)
            if command in {"resolve", "operator-close"}:
                note = cls._extract_natural_collab_note(
                    normalized,
                    ticket_id=ticket_id,
                    keyword=matched_keyword,
                )
                args.append(note or cls._COLLAB_DEFAULT_NOTES[command])
            elif command in {
                "priority",
                "assign",
                "merge",
                "link",
                "needs-info",
                "escalate",
                "reopen",
            }:
                rest = cls._extract_natural_collab_note(
                    normalized,
                    ticket_id=ticket_id,
                    keyword=matched_keyword,
                )
                if rest:
                    args.extend(rest.split())
            if command == "priority":
                args = cls._extract_priority_args(normalized, ticket_id, args)
            if command == "list":
                args = cls._parse_list_priority_args(normalized)
            return command, args, "natural_language_command"
        # English non-slash fallback.
        if lowered.startswith("claim "):
            rest = normalized[6:].strip()
            args = rest.split() if rest else []
            return "claim", args, "natural_language_command"
        if lowered.startswith("resolve "):
            rest = normalized[8:].strip()
            args = rest.split() if rest else []
            if args:
                return "resolve", args, "natural_language_command"
        if lowered.startswith("priority "):
            rest = normalized[9:].strip()
            args = rest.split() if rest else []
            if args:
                return "priority", args, "natural_language_command"
        if lowered.startswith("assign "):
            rest = normalized[7:].strip()
            args = rest.split() if rest else []
            if args:
                return "assign", args, "natural_language_command"
        return None

    @classmethod
    def _extract_natural_collab_note(
        cls,
        text: str,
        *,
        ticket_id: str | None,
        keyword: str,
    ) -> str:
        normalized = str(text or "")
        if ticket_id:
            normalized = re.sub(re.escape(ticket_id), " ", normalized, flags=re.IGNORECASE)
        normalized = normalized.replace(keyword, " ")
        normalized = normalized.replace("：", " ").replace(":", " ")
        normalized = re.sub(r"\s+", " ", normalized).strip(" ，,。；;！!？?")
        return normalized

    @classmethod
    def _parse_list_priority_args(cls, text: str) -> list[str]:
        lowered = text.lower()
        args = []
        if "p1" in lowered or ("紧急" in text) or ("重要紧急" in text):
            args.append("P1")
        elif "p2" in lowered or "加急" in text or "高优先" in text:
            args.append("P2")
        elif "p3" in lowered:
            args.append("P3")
        elif "p4" in lowered or "低优先" in text:
            args.append("P4")
        return args

    @classmethod
    def _extract_priority_args(
        cls,
        text: str,
        ticket_id: str | None,
        existing_args: list[str],
    ) -> list[str]:
        lowered = text.lower()
        has_priority = any(arg in ("P1", "P2", "P3", "P4") for arg in existing_args)
        args = list(existing_args)
        if ticket_id:
            args = [ticket_id] + args
        if has_priority:
            return args
        priority_found = False
        p1_keywords = (
            "紧急",
            "十万火急",
            "非常紧急",
            "立即",
            "马上",
            "重要紧急",
            "急",
            "p1",
            "urgent",
            "critical",
        )
        p2_keywords = ("加急", "高优先级", "优先", "尽快", "重要", "p2", "high")
        p4_keywords = ("不急", "不紧急", "低优先", "建议", "p4", "low", "enhancement")
        for kw in p1_keywords:
            if kw in lowered:
                args.append("P1")
                priority_found = True
                break
        if not priority_found:
            for kw in p2_keywords:
                if kw in lowered:
                    args.append("P2")
                    priority_found = True
                    break
        if not priority_found:
            for kw in p4_keywords:
                if kw in lowered:
                    args.append("P4")
                    priority_found = True
                    break
        if not priority_found:
            args.append("P1")
        return args

    def _build_collab_command_error_result(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
        command: str,
        command_source: str,
        requested_ticket_id: str,
        fallback_ticket_id: str | None,
        error: Exception,
    ) -> SupportIntakeResult:
        if self._ticket_api is None:
            raise RuntimeError("Ticket API is required for collaboration command error handling")
        fallback = str(fallback_ticket_id or "").strip() or None
        ticket = self._ticket_api.get_ticket(requested_ticket_id)
        if ticket is None and fallback:
            ticket = self._ticket_api.get_ticket(fallback)
        if ticket is None:
            ticket = Ticket(
                ticket_id=fallback or requested_ticket_id,
                channel=envelope.channel,
                session_id=envelope.session_id,
                thread_id=str(envelope.metadata.get("thread_id") or envelope.session_id),
                customer_id=None,
                title="协同命令执行失败",
                latest_message=str(envelope.message_text or ""),
                intent=disambiguation.intent.intent,
                priority="P3",
                status="open",
                queue="support",
                assignee=None,
                needs_handoff=False,
                metadata={"synthetic_ticket": True},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        events = (
            self._ticket_api.list_events(ticket.ticket_id)
            if self._ticket_api.get_ticket(ticket.ticket_id)
            else []
        )
        sla_result = self._build_clarification_sla(ticket, events)
        error_message = str(error)
        if isinstance(error, KeyError):
            reply_text = (
                f"未找到工单 {requested_ticket_id}，请确认工单号是否正确。"
                "你可以先发送“查询当前工单”获取有效工单号后再执行命令。"
            )
            failure_reason = "ticket_not_found"
        else:
            reply_text = (
                f"协同命令未执行成功：/{command}。"
                f"原因：{error_message or '命令被拒绝'}。"
                f"可重试：/{command} {requested_ticket_id} 备注说明。"
            )
            failure_reason = "command_rejected"
        reply_trace = {
            "provider": "fallback",
            "prompt_key": "collab_command_error_reply",
            "prompt_version": "v1",
            "generation_type": "collab_command",
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
            "command": command,
            "requested_ticket_id": requested_ticket_id,
            "ticket_id": ticket.ticket_id,
            "source": command_source,
            "error_type": error.__class__.__name__,
            "error_message": error_message,
            "failure_reason": failure_reason,
        }
        llm_trace: dict[str, object] = {
            "provider": "fallback",
            "model": None,
            "prompt_key": "collab_command_error_reply",
            "prompt_version": "v1",
            "success": True,
            "fallback_used": True,
            "degraded": False,
            "degrade_reason": None,
        }
        outcome = WorkflowOutcome(
            ticket=ticket,
            intent=disambiguation.intent,
            resolved_existing_ticket_id=ticket.ticket_id,
            retrieved_docs=[],
            summary=f"协同命令执行失败：/{command} ({failure_reason})",
            llm_trace=llm_trace,
            recommendations=[],
            handoff=HandoffDecision(
                should_handoff=False,
                reason="collab_command_failed",
                payload={
                    "command": command,
                    "requested_ticket_id": requested_ticket_id,
                    "failure_reason": failure_reason,
                },
            ),
            sla=sla_result,
            reply_text=reply_text,
            reply_trace=reply_trace,
            reply_generation_type="collab_command",
        )
        existing_ticket = self._ticket_api.get_ticket(ticket.ticket_id)
        if existing_ticket is not None:
            self._ticket_api.add_event(
                ticket.ticket_id,
                event_type="collab_command_failed",
                actor_type="agent",
                actor_id="support-intake",
                payload={
                    "command": command,
                    "requested_ticket_id": requested_ticket_id,
                    "failure_reason": failure_reason,
                    "error_type": error.__class__.__name__,
                    "error_message": error_message,
                },
            )
        return SupportIntakeResult(
            ticket_id=ticket.ticket_id,
            reply_text=reply_text,
            handoff=False,
            collab_push=None,
            outcome=outcome,
            ticket_action="collab_command_failed",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=ticket.queue,
            priority=ticket.priority,
            trace_events=["collab_command_failed", command],
            llm_trace=llm_trace,
            reply_trace=reply_trace,
        )

    def _resolve_active_ticket_id(
        self,
        *,
        envelope: InboundEnvelope,
        disambiguation: DisambiguationResult,
        requested_ticket_id: str | None,
    ) -> str | None:
        if requested_ticket_id:
            return str(requested_ticket_id).strip() or None
        for key in ("ticket_id", "active_ticket_id"):
            value = str(envelope.metadata.get(key) or "").strip()
            if value:
                return value
        session_context = envelope.metadata.get("session_context")
        if isinstance(session_context, dict):
            active = str(session_context.get("active_ticket_id") or "").strip()
            if active:
                return active
        active_from_disambiguation = str(disambiguation.active_ticket_id or "").strip()
        if active_from_disambiguation:
            return active_from_disambiguation
        suggested = str(disambiguation.suggested_ticket_id or "").strip()
        if suggested:
            return suggested
        if disambiguation.candidate_ticket_ids:
            first_candidate = str(disambiguation.candidate_ticket_ids[0]).strip()
            if first_candidate:
                return first_candidate
        return None

    @staticmethod
    def _resolve_actor_id(metadata: dict[str, object], *, session_id: str) -> str:
        for key in ("actor_id", "sender_id", "from_userid", "from_user_id", "userid", "user_id"):
            value = str(metadata.get(key) or "").strip()
            if value:
                return value
        normalized_session = str(session_id or "").strip()
        if normalized_session.startswith("group:") and ":user:" in normalized_session:
            suffix = normalized_session.rsplit(":user:", 1)[-1].strip()
            if suffix:
                return suffix
        if normalized_session.startswith("dm:"):
            suffix = normalized_session[3:].strip()
            if suffix:
                return suffix
        return "support-intake"

    @staticmethod
    def _render_collab_command_reply(*, command: str, ticket: Ticket | None, actor_id: str) -> str:
        if command == "claim":
            if ticket is None:
                return "认领失败：未找到工单。"
            assignee = ticket.assignee or actor_id
            return f"认领成功：{ticket.ticket_id}，当前处理人员：{assignee}。"
        if command == "resolve":
            if ticket is None:
                return "处理失败：未找到工单。"
            return f"工单 {ticket.ticket_id} 已处理完成，请确认是否恢复正常。"
        if command in {"customer-confirm", "close_compat"}:
            if ticket is None:
                return "操作失败：未找到工单。"
            return f"收到确认，工单 {ticket.ticket_id} 已关闭。"
        if command == "operator-close":
            if ticket is None:
                return "操作失败：未找到工单。"
            return f"已强制关闭 {ticket.ticket_id}，原因已记录。"
        if command == "end-session":
            return "当前会话已结束，可继续发起新问题。"
        if command == "list":
            if ticket is None:
                return "未找到符合条件的工单。"
            return f"找到工单 {ticket.ticket_id}，详情请查看工单列表。"
        return f"工单 {ticket.ticket_id if ticket else 'unknown'} 状态已更新。"

    @classmethod
    def _build_cross_group_sync_push(
        cls,
        *,
        source_session_id: str,
        command: str,
        ticket: Ticket,
        actor_id: str,
    ) -> dict[str, str] | None:
        source = str(source_session_id or "").strip()
        target = str(ticket.session_id or "").strip()
        if command not in {"claim", "resolve", "reassign"}:
            if not source or not target or source == target:
                return None
        message = cls._render_cross_group_sync_message(
            command=command,
            ticket=ticket,
            actor_id=actor_id,
        )
        if message is None:
            return None
        return {
            "ticket_id": ticket.ticket_id,
            "session_id": target,
            "message": message,
            "command": command,
            "source": "collab_command",
            "source_session_id": source,
        }

    @staticmethod
    def _render_cross_group_sync_message(
        *,
        command: str,
        ticket: Ticket,
        actor_id: str,
    ) -> str | None:
        if command == "claim":
            assignee = ticket.assignee or actor_id
            return f"工单 {ticket.ticket_id} 已由 {assignee} 正在处理（接手处理）。"
        if command == "resolve":
            return f"工单 {ticket.ticket_id} 已处理完成，请确认是否恢复正常。"
        if command in {"customer-confirm", "close_compat"}:
            return f"收到确认，工单 {ticket.ticket_id} 已关闭。"
        if command == "operator-close":
            reason = str(ticket.resolution_note or "").strip() or "未填写"
            return f"工单 {ticket.ticket_id} 已由处理工程师关闭，原因：{reason}。"
        if command == "end-session":
            return "当前会话已结束，可继续发起新问题。"
        return None

    def _should_push_to_collab(
        self,
        outcome: WorkflowOutcome,
        existing_ticket_id: str | None,
    ) -> bool:
        if self._case_collab_workflow is None:
            return False
        if existing_ticket_id is not None:
            return False
        if outcome.ticket.queue == "faq":
            return False
        return True

    def _record_intake_trace(self, envelope: InboundEnvelope, outcome: WorkflowOutcome) -> None:
        if self._ticket_api is None:
            return

        ticket_id = outcome.ticket.ticket_id
        grounding_sources = build_source_payloads(
            outcome.ticket.latest_message,
            [
                {"doc": doc, "score": doc.score, "rank": idx, "retrieval_mode": "hybrid"}
                for idx, doc in enumerate(outcome.retrieved_docs, start=1)
            ],
            top_k=5,
        )
        handoff_context = build_handoff_context(
            ticket=outcome.ticket,
            summary=build_handoff_summary(
                outcome.ticket,
                self._ticket_api.list_events(ticket_id),
                summary=outcome.summary,
            ),
            recommended_actions=[item.as_dict() for item in outcome.recommendations],
            grounding_sources=grounding_sources,
            trace_events=self._derive_ticket_action(outcome)[1],
            llm_trace=outcome.llm_trace,
        )
        lifecycle_stage = "awaiting_human" if outcome.handoff.should_handoff else "drafted"
        self._ticket_api.update_ticket(
            ticket_id,
            {
                "inbox": str(envelope.metadata.get("inbox") or outcome.ticket.inbox),
                "lifecycle_stage": lifecycle_stage,
                "first_response_due_at": outcome.sla.first_response_due_at,
                "resolution_due_at": outcome.sla.resolution_due_at,
                "metadata": {
                    "similar_case_ids": [
                        doc.doc_id
                        for doc in outcome.retrieved_docs
                        if doc.source_type == "history_case"
                    ][:5],
                    "similar_cases": [
                        {
                            "doc_id": doc.doc_id,
                            "source_type": doc.source_type,
                            "title": doc.title,
                            "score": doc.score,
                        }
                        for doc in outcome.retrieved_docs
                        if doc.source_type == "history_case"
                    ][:5],
                    "recommended_action_cards": [
                        item.as_dict() for item in outcome.recommendations
                    ],
                    "grounding_sources": grounding_sources,
                    "next_steps": [item.action for item in outcome.recommendations],
                    "risk_flags": sorted(
                        {item.risk for item in outcome.recommendations if item.risk}
                    ),
                    "llm_trace": dict(outcome.llm_trace),
                    "reply_trace": dict(outcome.reply_trace),
                    "reply_generation_type": outcome.reply_generation_type,
                    "ai_degraded": bool(outcome.llm_trace.get("degraded")),
                    HANDOFF_CONTEXT_KEY: handoff_context,
                },
            },
            actor_id="support-intake",
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_classified",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "intent": outcome.intent.intent,
                "confidence": outcome.intent.confidence,
                "reason": outcome.intent.reason,
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_context_retrieved",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "source_type": "faq" if outcome.intent.intent == "faq" else "grounded",
                "source_breakdown": sorted({doc.source_type for doc in outcome.retrieved_docs}),
                "doc_ids": [doc.doc_id for doc in outcome.retrieved_docs],
                "doc_titles": [doc.title for doc in outcome.retrieved_docs],
                "grounding_sources": grounding_sources,
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_draft_generated",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "reply_preview": outcome.reply_text[:200],
                "should_handoff": outcome.handoff.should_handoff,
                "reply_trace": dict(outcome.reply_trace),
                "generation_type": outcome.reply_generation_type,
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_reply_generated",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "generation_type": outcome.reply_generation_type,
                "reply_trace": dict(outcome.reply_trace),
                "reply_preview": outcome.reply_text[:200],
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_summary_generated",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "summary_preview": outcome.summary[:200],
                "llm_trace": dict(outcome.llm_trace),
            },
        )
        self._ticket_api.add_event(
            ticket_id,
            event_type="ticket_recommendations_generated",
            actor_type="agent",
            actor_id="support-intake",
            payload={
                "actions": [item.as_dict() for item in outcome.recommendations],
            },
        )
        if outcome.handoff.should_handoff:
            self._ticket_api.add_event(
                ticket_id,
                event_type="ticket_handoff_requested",
                actor_type="agent",
                actor_id="support-intake",
                payload={
                    "reason": outcome.handoff.reason,
                    "sla_targets": outcome.sla.escalation_targets,
                    "sla_policy_version": outcome.sla.policy_version,
                    "sla_rule_path": outcome.sla.matched_rule_path,
                    "handoff_policy_version": outcome.handoff.policy_version,
                    "handoff_rule_paths": list(outcome.handoff.matched_rule_paths),
                },
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="handoff_context_captured",
                actor_type="agent",
                actor_id="support-intake",
                payload={"context": handoff_context},
            )

    def _derive_ticket_action(self, outcome: WorkflowOutcome) -> tuple[str, list[str]]:
        trace_events: list[str] = []
        if outcome.handoff.should_handoff:
            trace_events.extend(["need_handoff", "push_human_queue"])
            return "handoff", trace_events

        if outcome.intent.is_low_confidence or (
            outcome.intent.confidence < self._handoff_confidence_threshold
        ):
            trace_events.extend(["low_confidence", "conservative_ticket"])
            return "conservative_ticket", trace_events

        if outcome.intent.intent == "greeting":
            trace_events.extend(["greeting", "direct_reply"])
            return "greeting_reply", trace_events

        if outcome.intent.intent == "faq":
            top_score = outcome.retrieved_docs[0].score if outcome.retrieved_docs else 0.0
            if top_score < self._faq_score_threshold:
                trace_events.extend(["faq_weak_hit", "conservative_ticket"])
                return "conservative_ticket", trace_events
            trace_events.extend(["faq_hit", "direct_reply"])
            return "faq_reply", trace_events

        if outcome.intent.intent == "progress_query":
            trace_events.extend(["progress_query", "direct_reply"])
            return "progress_reply", trace_events

        if outcome.ticket.status == "escalated":
            trace_events.extend(["status_escalated", "notify_collab"])
            return "escalate", trace_events

        if outcome.intent.confidence < self._intent_confidence_threshold:
            trace_events.extend(["below_intent_threshold", "conservative_ticket"])
            return "conservative_ticket", trace_events

        trace_events.extend(["create_ticket", "notify_collab"])
        return "create_ticket", trace_events
