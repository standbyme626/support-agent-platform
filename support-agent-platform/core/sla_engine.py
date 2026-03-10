from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from storage.models import Ticket, TicketEvent


@dataclass(frozen=True)
class SlaRule:
    first_response_minutes: int
    resolution_minutes: int
    escalation: str


@dataclass(frozen=True)
class SlaCheckResult:
    first_response_due_at: datetime
    resolution_due_at: datetime
    breached_items: list[str]
    escalation_targets: list[str]


class SlaEngine:
    def __init__(self, rules: dict[str, SlaRule]) -> None:
        self._rules = rules

    @classmethod
    def from_file(cls, path: Path) -> SlaEngine:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rules: dict[str, SlaRule] = {}
        for priority, rule_data in payload["rules"].items():
            rules[priority] = SlaRule(
                first_response_minutes=int(rule_data["first_response_minutes"]),
                resolution_minutes=int(rule_data["resolution_minutes"]),
                escalation=str(rule_data["escalation"]),
            )
        return cls(rules)

    def evaluate(
        self,
        ticket: Ticket,
        events: list[TicketEvent],
        *,
        now: datetime | None = None,
    ) -> SlaCheckResult:
        reference_now = now or datetime.now(UTC)
        rule = self._rules.get(ticket.priority)
        if rule is None:
            raise KeyError(f"No SLA rule for priority {ticket.priority}")

        created_at = ticket.created_at or reference_now
        first_due = created_at + timedelta(minutes=rule.first_response_minutes)
        resolution_due = created_at + timedelta(minutes=rule.resolution_minutes)

        first_response_done = any(
            event.event_type in {"assigned", "reassigned", "agent_reply"} for event in events
        )
        resolved = ticket.status in {"resolved", "closed"}

        breaches: list[str] = []
        if not first_response_done and reference_now > first_due:
            breaches.append("first_response_overdue")
        if not resolved and reference_now > resolution_due:
            breaches.append("resolution_overdue")

        escalation_targets: list[str] = []
        if breaches:
            escalation_targets.append(rule.escalation)

        return SlaCheckResult(
            first_response_due_at=first_due,
            resolution_due_at=resolution_due,
            breached_items=breaches,
            escalation_targets=escalation_targets,
        )
