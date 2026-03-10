from __future__ import annotations

from dataclasses import dataclass

from core.ticket_api import TicketAPI
from storage.models import Ticket


@dataclass(frozen=True)
class CaseCollabAction:
    command: str
    ticket: Ticket
    message: str


class CaseCollabWorkflow:
    """Workflow B: S1 new-ticket push + S2/S3/S4/S5 slash commands."""

    def __init__(self, ticket_api: TicketAPI) -> None:
        self._ticket_api = ticket_api

    def push_new_ticket(self, ticket_id: str) -> dict[str, str]:
        ticket = self._ticket_api.require_ticket(ticket_id)
        push_message = (
            f"[new-ticket] {ticket.ticket_id} | queue={ticket.queue} | "
            f"intent={ticket.intent} | priority={ticket.priority} | "
            f"commands: /claim /reassign <user> /escalate <reason> /close <note>"
        )
        self._ticket_api.add_event(
            ticket.ticket_id,
            event_type="collab_push",
            actor_type="system",
            actor_id="case-collab",
            payload={"message": push_message},
        )
        return {"ticket_id": ticket.ticket_id, "message": push_message}

    def handle_command(
        self, *, ticket_id: str, actor_id: str, command_line: str
    ) -> CaseCollabAction:
        command, args = self._parse_command(command_line)

        if command == "claim":
            updated = self._ticket_api.assign_ticket(
                ticket_id, assignee=actor_id, actor_id=actor_id
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
                ticket_id, assignee=assignee, actor_id=actor_id
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
            updated = self._ticket_api.close_ticket(
                ticket_id,
                actor_id=actor_id,
                resolution_note=resolution_note,
            )
            self._ticket_api.add_event(
                ticket_id,
                event_type="collab_close",
                actor_type="agent",
                actor_id=actor_id,
                payload={"resolution_note": resolution_note, "command": command_line},
            )
            return CaseCollabAction("close", updated, f"{ticket_id} closed")

        raise ValueError(f"Unsupported command: /{command}")

    @staticmethod
    def _parse_command(command_line: str) -> tuple[str, list[str]]:
        normalized = command_line.strip()
        if not normalized.startswith("/"):
            raise ValueError("Command must start with '/'")

        parts = normalized[1:].split()
        if not parts:
            raise ValueError("Empty command")

        return parts[0].lower(), parts[1:]
