from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from core.hitl.approval_policy import ApprovalPolicy
from core.hitl.approval_runtime import ApprovalRuntime
from core.hitl.handoff_context import build_approval_context
from core.ticket_api import TicketAPI
from storage.models import Ticket


@dataclass(frozen=True)
class CaseCollabAction:
    command: str
    ticket: Ticket
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

    def __init__(
        self,
        ticket_api: TicketAPI,
        *,
        approval_runtime: ApprovalRuntime | None = None,
    ) -> None:
        self._ticket_api = ticket_api
        self._approval_runtime = approval_runtime or ApprovalRuntime(
            ticket_api=ticket_api,
            policy=ApprovalPolicy.default(),
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
                else ("collab_customer_confirm" if command == "customer-confirm" else "collab_operator_close")
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

        raise ValueError(f"Unsupported command: /{command}")

    def _build_collab_payload(self, ticket: Ticket) -> dict[str, object]:
        recent_events = self._ticket_api.list_events(ticket.ticket_id)
        summary = f"{ticket.title} | latest={ticket.latest_message[:80]}"
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
