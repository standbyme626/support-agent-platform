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
from storage.models import InboundEnvelope, Ticket, TicketEvent

from .case_collab_workflow import CaseCollabWorkflow


@dataclass(frozen=True)
class SupportIntakeResult:
    ticket_id: str
    reply_text: str
    handoff: bool
    collab_push: dict[str, str] | None
    outcome: WorkflowOutcome
    ticket_action: str
    summary: str
    recommended_actions: list[dict[str, object]]
    handoff_required: bool
    queue: str
    priority: str
    trace_events: list[str]
    llm_trace: dict[str, object]
    reply_trace: dict[str, object]


class SupportIntakeWorkflow:
    """Workflow A: intake entry -> FAQ reply -> auto-ticket -> handoff.

    Business routing/transition rules are enforced here (workflow/core),
    not inside the OpenClaw ingress/session/routing adapter layer.
    """

    _COLLAB_COMMAND_RE = re.compile(r"^\s*/(?P<command>[a-zA-Z][\w-]*)(?:\s+(?P<rest>.*))?\s*$")
    _TICKET_ID_RE = re.compile(r"^(?:TCK-[A-Za-z0-9_-]+|TICKET-[A-Za-z0-9_-]+)$")
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
    ) -> None:
        self._workflow_engine = workflow_engine
        self._case_collab_workflow = case_collab_workflow
        self._ticket_api = ticket_api or getattr(case_collab_workflow, "_ticket_api", None)
        self._intent_confidence_threshold = intent_confidence_threshold
        self._faq_score_threshold = faq_score_threshold
        self._handoff_confidence_threshold = handoff_confidence_threshold

    def run(
        self,
        envelope: InboundEnvelope,
        *,
        existing_ticket_id: str | None = None,
    ) -> SupportIntakeResult:
        disambiguation = self._workflow_engine.assess_disambiguation(
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

        resolved_existing_ticket_id = self._workflow_engine.resolve_existing_ticket_id(
            envelope_with_disambiguation,
            requested_ticket_id=existing_ticket_id,
        )

        envelope_for_processing = envelope_with_disambiguation
        if disambiguation.decision == "new_issue_detected":
            resolved_existing_ticket_id = None
            envelope_for_processing = self._tag_new_issue_context(
                envelope_with_disambiguation,
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

        reply_text = outcome.reply_text
        if collab_push is not None:
            session_mode = ""
            session_context = envelope_with_disambiguation.metadata.get("session_context")
            if isinstance(session_context, dict):
                session_mode = str(session_context.get("session_mode") or "").strip()
            if session_mode == "awaiting_new_issue":
                reply_text = "已按新会话处理，并创建/关联新工单上下文。"
            elif (
                disambiguation.decision == "new_issue_detected"
                and disambiguation.reason == "session_mode_awaiting_new_issue"
            ):
                reply_text = "已按新会话处理，并创建/关联新工单上下文。"
            elif disambiguation.decision == "new_issue_detected":
                reply_text = "已开启新问题处理流程，正在为你生成新的工单记录。"
            else:
                reply_text = (
                    f"已创建工单 {outcome.ticket.ticket_id}，状态：待认领。已通知处理同学。"
                )

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

        active_ticket_id = self._resolve_active_ticket_id(
            envelope=envelope,
            disambiguation=disambiguation,
            requested_ticket_id=None,
        )
        if active_ticket_id is not None:
            ticket = self._ticket_api.get_ticket(active_ticket_id)
        else:
            ticket = None
        if ticket is None:
            return None

        self._ticket_api.reset_session_context(
            envelope.session_id,
            metadata={
                "session_mode": "awaiting_new_issue",
                "last_intent": "new_issue_requested",
                "disambiguation_reason": disambiguation.reason,
            },
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
        if (
            disambiguation.decision == "continue_current"
            and disambiguation.reason in {"explicit_ticket_in_message", "requested_ticket_id"}
        ):
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
        command, args = parsed

        active_ticket_id = self._resolve_active_ticket_id(
            envelope=envelope,
            disambiguation=disambiguation,
            requested_ticket_id=existing_ticket_id,
        )
        ticket_id = active_ticket_id
        command_args = list(args)
        if command_args and self._TICKET_ID_RE.match(command_args[0]):
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
        except (KeyError, ValueError):
            return self._build_collab_usage_result(
                disambiguation=disambiguation,
                command=command,
                fallback_ticket_id=ticket_id,
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
            "source": "slash_command",
        }
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
            collab_push=None,
            outcome=outcome,
            ticket_action=f"collab_{resolved_command.replace('-', '_')}",
            summary=outcome.summary,
            recommended_actions=[],
            handoff_required=False,
            queue=ticket.queue,
            priority=ticket.priority,
            trace_events=["collab_command", resolved_command],
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
        disambiguation: DisambiguationResult,
        command: str,
        fallback_ticket_id: str | None,
    ) -> SupportIntakeResult:
        ticket_id = fallback_ticket_id or disambiguation.active_ticket_id or disambiguation.suggested_ticket_id
        if ticket_id is None or self._ticket_api is None:
            raise ValueError("ticket_id is required for collaboration command")
        ticket = self._ticket_api.require_ticket(ticket_id)
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
    def _parse_collab_command(cls, message_text: str) -> tuple[str, list[str]] | None:
        match = cls._COLLAB_COMMAND_RE.match(str(message_text or ""))
        if match is None:
            return None
        command = str(match.group("command") or "").strip().lower().replace("_", "-")
        if command not in {
            "claim",
            "resolve",
            "customer-confirm",
            "operator-close",
            "end-session",
            "close",
        }:
            return None
        raw_rest = str(match.group("rest") or "").strip()
        args = raw_rest.split() if raw_rest else []
        return command, args

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
    def _render_collab_command_reply(*, command: str, ticket: Ticket, actor_id: str) -> str:
        if command == "claim":
            assignee = ticket.assignee or actor_id
            return f"认领成功：{ticket.ticket_id}，当前处理人：{assignee}。"
        if command == "resolve":
            return f"工单 {ticket.ticket_id} 已处理完成，请确认是否恢复正常。"
        if command in {"customer-confirm", "close_compat"}:
            return f"收到确认，工单 {ticket.ticket_id} 已关闭。"
        if command == "operator-close":
            return f"已强制关闭 {ticket.ticket_id}，原因已记录。"
        if command == "end-session":
            return "当前会话已结束，可继续发起新问题。"
        return f"工单 {ticket.ticket_id} 状态已更新。"

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
