from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from core.hitl.approval_policy import ApprovalPolicy
from core.hitl.approval_runtime import ApprovalRuntime
from core.hitl.handoff_context import build_approval_context
from core.summary_engine import compact_summary_text
from core.ticket_api import TicketAPI
from storage.models import Ticket


@dataclass(frozen=True)
class CaseCollabAction:
    command: str
    ticket: Ticket | None
    message: str


class CaseCollabWorkflow:
    """Workflow B: S1 new-ticket push + S2/S3/S4/S5 slash commands."""

    _STATE_SET: ClassVar[frozenset[str]] = frozenset(
        {
            "pending_claim",
            "claimed",
            "waiting_customer",
            "waiting_internal",
            "pending_approval",
            "escalated",
            "resolved",
            "closed",
            "completed",
        }
    )
    _DEFAULT_COLLAB_LATEST_MESSAGE_MAX_CHARS: ClassVar[int] = 480
    _COLLAB_LATEST_MESSAGE_MAX_CHARS_ENV: ClassVar[str] = (
        "SUPPORT_AGENT_COLLAB_LATEST_MESSAGE_MAX_CHARS"
    )

    def __init__(
        self,
        ticket_api: TicketAPI,
        *,
        approval_runtime: ApprovalRuntime | None = None,
        latest_message_max_chars: int | None = None,
    ) -> None:
        self._ticket_api = ticket_api
        self._approval_runtime = approval_runtime or ApprovalRuntime(
            ticket_api=ticket_api,
            policy=ApprovalPolicy.default(),
        )
        self._collab_latest_message_max_chars = self._resolve_latest_message_max_chars(
            override=latest_message_max_chars
        )

    def push_new_ticket(self, ticket_id: str) -> dict[str, str]:
        ticket = self._ticket_api.require_ticket(ticket_id)
        if ticket.handoff_state == "none":
            ticket = self._ticket_api.update_ticket(
                ticket.ticket_id,
                {"handoff_state": "pending_claim", "last_agent_action": "collab_push"},
                actor_id="case-collab",
            )
        payload = self._build_collab_payload(ticket)
        push_message = self._render_push_message(ticket, payload)
        self._ticket_api.add_event(
            ticket.ticket_id,
            event_type="collab_push",
            actor_type="system",
            actor_id="case-collab",
            payload=payload | {"message": push_message},
        )
        return {"ticket_id": ticket.ticket_id, "message": push_message}

    def handle_command(
        self, *, ticket_id: str, actor_id: str, command_line: str
    ) -> CaseCollabAction:
        command, args = self._parse_command(command_line)
        command = self._normalize_command(command)
        close_compat_mode = command == "close"
        if close_compat_mode:
            command = "customer-confirm"

        if command == "claim":
            updated = self._ticket_api.assign_ticket(
                ticket_id,
                assignee=actor_id,
                actor_id=actor_id,
            )
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {"handoff_state": "claimed", "last_agent_action": "claim"},
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_claim",
                actor_type="agent",
                actor_id=actor_id,
                payload={"command": command_line},
            )
            return CaseCollabAction("claim", updated, f"{actor_id} claimed {ticket_id}")

        if command == "reassign":
            if not args:
                raise ValueError("/reassign requires target assignee")
            assignee = args[0]
            request = self._approval_runtime.request_approval_if_needed(
                ticket_id=ticket_id,
                action_type="reassign",
                actor_id=actor_id,
                payload={
                    "actor_id": actor_id,
                    "target_assignee": assignee,
                },
                context=build_approval_context(
                    ticket=self._ticket_api.require_ticket(ticket_id),
                    action_type="reassign",
                    command_line=command_line,
                    payload={"target_assignee": assignee},
                ),
            )
            if request.requires_approval and request.pending_action is not None:
                self._ticket_api.add_event(
                    ticket_id,
                    event_type="collab_reassign_pending_approval",
                    actor_type="agent",
                    actor_id=actor_id,
                    payload={
                        "approval_id": request.pending_action.approval_id,
                        "target_assignee": assignee,
                        "command": command_line,
                    },
                )
                return CaseCollabAction(
                    "reassign",
                    request.ticket,
                    (
                        f"{ticket_id} reassign pending approval "
                        f"({request.pending_action.approval_id})"
                    ),
                )
            updated = self._ticket_api.assign_ticket(
                ticket_id,
                assignee=assignee,
                actor_id=actor_id,
            )
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {"handoff_state": "waiting_internal", "last_agent_action": f"reassign:{assignee}"},
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_reassign",
                actor_type="agent",
                actor_id=actor_id,
                payload={"to": assignee, "command": command_line},
            )
            return CaseCollabAction(
                "reassign",
                updated,
                f"{ticket_id} reassigned to {assignee} by {actor_id}",
            )

        if command == "escalate":
            reason = " ".join(args).strip() or "manual escalation"
            request = self._approval_runtime.request_approval_if_needed(
                ticket_id=ticket_id,
                action_type="escalate",
                actor_id=actor_id,
                payload={"actor_id": actor_id, "note": reason},
                context=build_approval_context(
                    ticket=self._ticket_api.require_ticket(ticket_id),
                    action_type="escalate",
                    command_line=command_line,
                    payload={"note": reason},
                ),
            )
            if request.requires_approval and request.pending_action is not None:
                self._ticket_api.add_event(
                    ticket_id,
                    event_type="collab_escalate_pending_approval",
                    actor_type="agent",
                    actor_id=actor_id,
                    payload={
                        "approval_id": request.pending_action.approval_id,
                        "reason": reason,
                        "command": command_line,
                    },
                )
                return CaseCollabAction(
                    "escalate",
                    request.ticket,
                    (
                        f"{ticket_id} escalation pending approval "
                        f"({request.pending_action.approval_id})"
                    ),
                )
            updated = self._ticket_api.escalate_ticket(
                ticket_id,
                actor_id=actor_id,
                reason=reason,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_escalate",
                actor_type="agent",
                actor_id=actor_id,
                payload={"reason": reason, "command": command_line},
            )
            return CaseCollabAction("escalate", updated, f"{ticket_id} escalated: {reason}")

        if command in {"customer-confirm", "operator-close"}:
            resolution_note = " ".join(args).strip()
            if not resolution_note:
                raise ValueError(f"/{command} requires resolution note")
            final_action_trail = [
                item.event_type for item in self._ticket_api.list_events(ticket_id)[-8:]
            ]
            close_reason = (
                "customer_confirmed" if command == "customer-confirm" else "operator_forced_close"
            )
            resolution_code = (
                "COLLAB_CUSTOMER_CONFIRMED"
                if command == "customer-confirm"
                else "COLLAB_OPERATOR_CLOSED"
            )
            updated = self._ticket_api.close_ticket(
                ticket_id,
                actor_id=actor_id,
                resolution_note=resolution_note,
                close_reason=close_reason,
                resolution_code=resolution_code,
                handoff_state="completed",
                metadata={
                    **self._ticket_api.require_ticket(ticket_id).metadata,
                    "final_action_trail": final_action_trail,
                    "resolved_action": ("close_compat" if close_compat_mode else command),
                },
            )
            event_type = (
                "collab_close"
                if close_compat_mode
                else (
                    "collab_customer_confirm"
                    if command == "customer-confirm"
                    else "collab_operator_close"
                )
            )
            event_payload = {
                "resolution_note": resolution_note,
                "command": command_line,
                "final_action_trail": final_action_trail,
                "resolved_action": command,
            }
            if close_compat_mode:
                event_payload["compatibility_mode"] = "slash_close_alias_customer_confirm"
            self._ticket_api.add_event(
                ticket_id,
                event_type=event_type,
                actor_type="agent",
                actor_id=actor_id,
                payload=event_payload,
            )

            dm_session_id = f"dm:{updated.customer_id}"
            try:
                self._ticket_api.reset_session_context(
                    dm_session_id,
                    metadata={
                        "session_mode": "awaiting_new_issue",
                        "last_intent": f"ticket_{command}_completed",
                        "updated_by": actor_id,
                    },
                )
            except Exception:
                pass

            action_name = "close_compat" if close_compat_mode else command
            return CaseCollabAction(action_name, updated, f"{ticket_id} closed")

        if command == "end-session":
            reason = " ".join(args).strip() or "manual_end_session"
            ticket = self._ticket_api.require_ticket(ticket_id)
            self._ticket_api.reset_session_context(
                ticket.session_id,
                metadata={
                    "session_mode": "awaiting_new_issue",
                    "last_intent": "session_end_requested",
                    "updated_by": actor_id,
                    "session_control_action": "session_end",
                    "session_control_reason": reason,
                },
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_session_end_requested",
                actor_type="agent",
                actor_id=actor_id,
                payload={
                    "session_id": ticket.session_id,
                    "reason": reason,
                    "command": command_line,
                },
            )
            refreshed = self._ticket_api.require_ticket(ticket_id)
            return CaseCollabAction(
                "end-session",
                refreshed,
                f"{ticket.session_id} session ended by {actor_id}",
            )

        if command == "resolve":
            resolution_note = " ".join(args).strip()
            if not resolution_note:
                raise ValueError("/resolve requires resolution note")
            updated = self._ticket_api.resolve_ticket(
                ticket_id,
                actor_id=actor_id,
                resolution_note=resolution_note,
                resolution_code="COLLAB_RESOLVED",
            )
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {"handoff_state": "waiting_customer", "last_agent_action": "resolve"},
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_resolve",
                actor_type="agent",
                actor_id=actor_id,
                payload={"resolution_note": resolution_note, "command": command_line},
            )

            dm_session_id = f"dm:{updated.customer_id}"
            try:
                self._ticket_api.reset_session_context(
                    dm_session_id,
                    metadata={
                        "session_mode": "awaiting_new_issue",
                        "last_intent": "ticket_resolved",
                        "updated_by": actor_id,
                    },
                )
            except Exception:
                pass

            return CaseCollabAction("resolve", updated, f"{ticket_id} resolved")

        if command == "state":
            if not args:
                raise ValueError("/state requires target collab state")
            target_state = args[0].strip().lower()
            if target_state not in self._STATE_SET:
                raise ValueError(f"Unsupported collab state: {target_state}")
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {"handoff_state": target_state, "last_agent_action": f"state:{target_state}"},
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_state_changed",
                actor_type="agent",
                actor_id=actor_id,
                payload={"to_state": target_state, "command": command_line},
            )
            return CaseCollabAction("state", updated, f"{ticket_id} state -> {target_state}")

        if command == "reopen":
            reason = " ".join(args).strip() or "manual_reopen"
            ticket = self._ticket_api.require_ticket(ticket_id)
            if ticket.status != "closed":
                raise ValueError(f"Cannot reopen ticket {ticket_id}: status is {ticket.status}")
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {
                    "status": "open",
                    "handoff_state": "in_progress",
                    "lifecycle_stage": "in_progress",
                    "resolution_note": None,
                    "resolution_code": None,
                    "closed_at": None,
                    "resolved_at": None,
                    "last_agent_action": "reopen",
                },
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_reopen",
                actor_type="agent",
                actor_id=actor_id,
                payload={"reason": reason, "command": command_line},
            )
            return CaseCollabAction("reopen", updated, f"{ticket_id} reopened: {reason}")

        if command == "priority":
            if not args:
                priority = "P1"
            else:
                priority = args[0].strip().upper()
                if priority not in {"P1", "P2", "P3", "P4"}:
                    raise ValueError(f"Invalid priority: {priority}. Use P1/P2/P3/P4")
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {"priority": priority, "last_agent_action": f"priority:{priority}"},
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_priority_changed",
                actor_type="agent",
                actor_id=actor_id,
                payload={"priority": priority, "command": command_line},
            )
            return CaseCollabAction("priority", updated, f"{ticket_id} priority -> {priority}")

        if command == "status":
            ticket = self._ticket_api.require_ticket(ticket_id)
            status_info = {
                "ticket_id": ticket.ticket_id,
                "status": ticket.status,
                "priority": ticket.priority,
                "assignee": ticket.assignee,
                "handoff_state": ticket.handoff_state,
                "created_at": str(ticket.created_at) if ticket.created_at else None,
                "updated_at": str(ticket.updated_at) if ticket.updated_at else None,
            }
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_status_query",
                actor_type="agent",
                actor_id=actor_id,
                payload={"command": command_line},
            )
            return CaseCollabAction("status", ticket, f"status: {status_info}")

        if command == "needs-info":
            note = " ".join(args).strip() or "需要补充信息"
            ticket = self._ticket_api.require_ticket(ticket_id)
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {
                    "handoff_state": "pending_customer",
                    "last_agent_action": "needs_info",
                },
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_needs_info",
                actor_type="agent",
                actor_id=actor_id,
                payload={"note": note, "command": command_line},
            )
            return CaseCollabAction("needs-info", updated, f"{ticket_id} needs info: {note}")

        if command == "merge":
            if not args:
                raise ValueError("/merge requires target ticket ID")
            valid_ids = [
                a for a in args if a.upper().startswith("TCK-") or a.upper().startswith("TICKET-")
            ]
            target_ticket_id = valid_ids[-1].strip() if valid_ids else args[-1].strip()
            source_ticket = self._ticket_api.require_ticket(ticket_id)
            target_ticket = self._ticket_api.require_ticket(target_ticket_id)
            if source_ticket.status == "closed":
                raise ValueError(f"Cannot merge from closed ticket {ticket_id}")
            metadata = dict(source_ticket.metadata)
            metadata["merged_from"] = ticket_id
            metadata["merge_timestamp"] = str(datetime.now())
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {
                    "status": "closed",
                    "handoff_state": "completed",
                    "lifecycle_stage": "resolved",
                    "resolution_note": f"已合并到工单 {target_ticket_id}",
                    "resolution_code": "MERGED",
                    "last_agent_action": "merge",
                    "metadata": metadata,
                },
                actor_id=actor_id,
            )
            target_metadata = dict(target_ticket.metadata)
            target_metadata["merged_tickets"] = list(target_metadata.get("merged_tickets", [])) + [
                ticket_id
            ]
            self._ticket_api.update_ticket(
                target_ticket_id,
                {
                    "latest_message": f"{source_ticket.latest_message}\n\n[已合并工单 {ticket_id}]",
                    "metadata": target_metadata,
                    "last_agent_action": "merge_received",
                },
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_merge",
                actor_type="agent",
                actor_id=actor_id,
                payload={
                    "target_ticket_id": target_ticket_id,
                    "command": command_line,
                },
            )
            self._ticket_api.add_event(
                target_ticket_id,
                event_type="collab_merged",
                actor_type="agent",
                actor_id=actor_id,
                payload={
                    "source_ticket_id": ticket_id,
                    "command": command_line,
                },
            )
            return CaseCollabAction("merge", updated, f"{ticket_id} merged to {target_ticket_id}")

        if command == "link":
            if not args:
                raise ValueError("/link requires target ticket ID")
            valid_ids = [
                a for a in args if a.upper().startswith("TCK-") or a.upper().startswith("TICKET-")
            ]
            target_ticket_id = valid_ids[-1].strip() if valid_ids else args[-1].strip()
            ticket = self._ticket_api.require_ticket(ticket_id)
            metadata = dict(ticket.metadata)
            linked_tickets = list(metadata.get("linked_tickets", []))
            if target_ticket_id not in linked_tickets:
                linked_tickets.append(target_ticket_id)
                metadata["linked_tickets"] = linked_tickets
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {
                    "metadata": metadata,
                    "last_agent_action": "link",
                },
                actor_id=actor_id,
            )
            target_ticket = self._ticket_api.require_ticket(target_ticket_id)
            target_metadata = dict(target_ticket.metadata)
            target_linked = list(target_metadata.get("linked_tickets", []))
            if ticket_id not in target_linked:
                target_linked.append(ticket_id)
                target_metadata["linked_tickets"] = target_linked
                self._ticket_api.update_ticket(
                    target_ticket_id,
                    {"metadata": target_metadata},
                    actor_id=actor_id,
                )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_link",
                actor_type="agent",
                actor_id=actor_id,
                payload={
                    "linked_ticket_id": target_ticket_id,
                    "command": command_line,
                },
            )
            return CaseCollabAction("link", updated, f"{ticket_id} linked to {target_ticket_id}")

        if command == "assign":
            if not args:
                raise ValueError("/assign requires target assignee")
            assignee = args[0].strip()
            updated = self._ticket_api.assign_ticket(
                ticket_id,
                assignee=assignee,
                actor_id=actor_id,
            )
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {"handoff_state": "waiting_internal", "last_agent_action": f"assign:{assignee}"},
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_assign",
                actor_type="agent",
                actor_id=actor_id,
                payload={"assignee": assignee, "command": command_line},
            )
            return CaseCollabAction("assign", updated, f"{ticket_id} assigned to {assignee}")

        if command == "list":
            priority_filter = None
            status_filter = None
            assignee_filter = None

            rest = " ".join(args).strip().lower() if args else ""

            if "p1" in rest or "紧急" in rest or "高优先" in rest:
                priority_filter = "P1"
            elif "p2" in rest:
                priority_filter = "P2"
            elif "p3" in rest:
                priority_filter = "P3"
            elif "p4" in rest or "低优先" in rest:
                priority_filter = "P4"

            if "待处理" in rest:
                status_filter = "open"
            elif "处理中" in rest:
                status_filter = "handoff"
            elif "已完结" in rest or "已完成" in rest:
                status_filter = "closed"

            if "我的" in rest:
                assignee_filter = actor_id

            all_tickets = self._ticket_api.list_tickets(limit=100)
            filtered = all_tickets

            if priority_filter:
                filtered = [t for t in filtered if t.priority == priority_filter]
            if status_filter:
                filtered = [t for t in filtered if t.status == status_filter]
            if assignee_filter:
                filtered = [t for t in filtered if t.assignee == assignee_filter]

            ticket_list = []
            for t in filtered[:20]:
                ticket_list.append(
                    {
                        "id": t.ticket_id,
                        "title": t.title[:30],
                        "status": t.status,
                        "priority": t.priority,
                        "assignee": t.assignee,
                    }
                )

            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_list_tickets",
                actor_type="agent",
                actor_id=actor_id,
                payload={
                    "priority_filter": priority_filter,
                    "status_filter": status_filter,
                    "count": len(ticket_list),
                    "command": command_line,
                },
            )

            return CaseCollabAction(
                "list", filtered[0] if filtered else None, f"Found {len(ticket_list)} tickets"
            )

        raise ValueError(f"Unsupported command: /{command}")

    def _build_collab_payload(self, ticket: Ticket) -> dict[str, object]:
        recent_events = self._ticket_api.list_events(ticket.ticket_id)
        latest_preview = compact_summary_text(
            ticket.latest_message,
            max_chars=self._collab_latest_message_max_chars,
        )
        summary = f"{ticket.title} | latest={latest_preview}"
        similar_case_cards = list(ticket.metadata.get("similar_cases", []))[:3]
        similar_cases = (
            [str(item.get("doc_id", "")) for item in similar_case_cards if isinstance(item, dict)]
            if similar_case_cards
            else list(ticket.metadata.get("similar_case_ids", []))[:3]
        )
        risk_flags: list[str] = []
        metadata_risks = ticket.metadata.get("risk_flags", [])
        if isinstance(metadata_risks, list):
            risk_flags.extend(str(item) for item in metadata_risks[:5])
        if ticket.risk_level in {"high", "medium"}:
            risk_flags.append(f"risk={ticket.risk_level}")
        if ticket.status == "escalated":
            risk_flags.append("status=escalated")
        if ticket.intent == "complaint":
            risk_flags.append("complaint")

        default_steps = [
            "先 /claim 认领",
            "确认上下文后 /resolve 或 /escalate",
        ]
        metadata_steps = ticket.metadata.get("next_steps", [])
        recommended_steps = (
            [str(item) for item in metadata_steps if str(item).strip()][:4]
            if isinstance(metadata_steps, list) and metadata_steps
            else default_steps
        )
        if ticket.priority == "P1":
            recommended_steps.insert(0, "优先升级处理")

        deduped_risk_flags: list[str] = []
        for item in risk_flags:
            if item not in deduped_risk_flags:
                deduped_risk_flags.append(item)

        return {
            "summary": summary,
            "similar_cases": similar_cases,
            "similar_case_cards": similar_case_cards,
            "recommended_steps": recommended_steps,
            "risk_flags": deduped_risk_flags,
            "sla_remaining": self._sla_remaining(ticket),
            "recent_events": [item.event_type for item in recent_events[-5:]],
        }

    @staticmethod
    def _sla_remaining(ticket: Ticket) -> dict[str, str]:
        now = datetime.now(UTC)
        first_response = "-"
        resolution = "-"
        if ticket.first_response_due_at:
            delta = ticket.first_response_due_at - now
            first_response = f"{int(delta.total_seconds() // 60)}m"
        if ticket.resolution_due_at:
            delta = ticket.resolution_due_at - now
            resolution = f"{int(delta.total_seconds() // 60)}m"
        return {"first_response": first_response, "resolution": resolution}

    def _render_push_message(self, ticket: Ticket, payload: dict[str, object]) -> str:
        first_response_due = (
            ticket.first_response_due_at.isoformat() if ticket.first_response_due_at else "-"
        )
        resolution_due = ticket.resolution_due_at.isoformat() if ticket.resolution_due_at else "-"
        return (
            f"[new-ticket] {ticket.ticket_id} | inbox={ticket.inbox} | queue={ticket.queue} | "
            f"intent={ticket.intent} | priority={ticket.priority} | "
            f"status={ticket.status}/{ticket.lifecycle_stage}/{ticket.handoff_state} | "
            f"sla(first={first_response_due}, resolution={resolution_due}) | "
            f"sla_remaining={payload['sla_remaining']} | summary={payload['summary']} | "
            f"risk={payload['risk_flags']} | similar={payload['similar_cases']} | "
            f"next={payload['recommended_steps']} | "
            f"commands: /claim /reassign <user> /escalate <reason> /resolve <note> "
            f"/customer-confirm <note> /operator-close <note> /end-session [reason] "
            f"/close <note>(compat) /state <state>"
        )

    @staticmethod
    def _parse_command(command_line: str) -> tuple[str, list[str]]:
        normalized = command_line.strip()
        if not normalized.startswith("/"):
            raise ValueError("Command must start with '/'")

        parts = normalized[1:].split()
        if not parts:
            raise ValueError("Empty command")

        return parts[0].lower(), parts[1:]

    @staticmethod
    def _normalize_command(command: str) -> str:
        return command.strip().lower().replace("_", "-")

    @classmethod
    def _resolve_latest_message_max_chars(cls, *, override: int | None) -> int:
        if isinstance(override, int) and override > 0:
            return override
        raw = str(os.getenv(cls._COLLAB_LATEST_MESSAGE_MAX_CHARS_ENV, "")).strip()
        if raw:
            try:
                parsed = int(raw)
                if parsed > 0:
                    return parsed
            except ValueError:
                pass
        return cls._DEFAULT_COLLAB_LATEST_MESSAGE_MAX_CHARS
