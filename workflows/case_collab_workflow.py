from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

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

    def __init__(self, ticket_api: TicketAPI) -> None:
        self._ticket_api = ticket_api

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
            updated = self._ticket_api.escalate_ticket(
                ticket_id,
                actor_id=actor_id,
                reason=reason,
            )
            updated = self._ticket_api.update_ticket(
                ticket_id,
                {
                    "handoff_state": "pending_approval",
                    "last_agent_action": "escalate",
                    "risk_level": "high",
                },
                actor_id=actor_id,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_escalate",
                actor_type="agent",
                actor_id=actor_id,
                payload={"reason": reason, "command": command_line},
            )
            return CaseCollabAction("escalate", updated, f"{ticket_id} escalated: {reason}")

        if command == "close":
            resolution_note = " ".join(args).strip()
            if not resolution_note:
                raise ValueError("/close requires resolution note")
            final_action_trail = [
                item.event_type for item in self._ticket_api.list_events(ticket_id)[-8:]
            ]
            updated = self._ticket_api.close_ticket(
                ticket_id,
                actor_id=actor_id,
                resolution_note=resolution_note,
                close_reason="customer_confirmed",
                resolution_code="COLLAB_CLOSED",
                handoff_state="completed",
                metadata={
                    **self._ticket_api.require_ticket(ticket_id).metadata,
                    "final_action_trail": final_action_trail,
                },
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_close",
                actor_type="agent",
                actor_id=actor_id,
                payload={
                    "resolution_note": resolution_note,
                    "command": command_line,
                    "final_action_trail": final_action_trail,
                },
            )
            return CaseCollabAction("close", updated, f"{ticket_id} closed")

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
        similar_cases = ticket.metadata.get("similar_case_ids", [])[:3]
        risk_flags: list[str] = []
        if ticket.risk_level in {"high", "medium"}:
            risk_flags.append(f"risk={ticket.risk_level}")
        if ticket.status == "escalated":
            risk_flags.append("status=escalated")
        if ticket.intent == "complaint":
            risk_flags.append("complaint")

        recommended_steps = [
            "先 /claim 认领",
            "确认上下文后 /resolve 或 /escalate",
        ]
        if ticket.priority == "P1":
            recommended_steps.insert(0, "优先升级处理")

        return {
            "summary": summary,
            "similar_cases": similar_cases,
            "recommended_steps": recommended_steps,
            "risk_flags": risk_flags,
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
            f"summary={payload['summary']} | risk={payload['risk_flags']} | "
            f"similar={payload['similar_cases']} | next={payload['recommended_steps']} | "
            f"commands: /claim /reassign <user> /escalate <reason> /resolve <note> "
            f"/close <note> /state <state>"
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
