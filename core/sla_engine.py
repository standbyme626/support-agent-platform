from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from storage.models import Ticket, TicketEvent

_DEFAULT_FIRST_RESPONSE_MINUTES = 60
_DEFAULT_RESOLUTION_MINUTES = 480
_DEFAULT_ESCALATION_TARGET = "queue"
_DEFAULT_ESCALATE_ON_BREACHES = ("first_response_overdue", "resolution_overdue")
_FIRST_RESPONSE_EVENT_TYPES = frozenset(
    {"assigned", "reassigned", "agent_reply", "ticket_assigned"}
)


@dataclass(frozen=True)
class MatchScope:
    intents: frozenset[str]
    priorities: frozenset[str]
    queues: frozenset[str]
    channels: frozenset[str]

    @classmethod
    def any(cls) -> MatchScope:
        return cls(
            intents=frozenset(),
            priorities=frozenset(),
            queues=frozenset(),
            channels=frozenset(),
        )

    @classmethod
    def from_payload(cls, payload: object) -> MatchScope:
        if not isinstance(payload, Mapping):
            return cls.any()
        return cls(
            intents=_normalize_collection(payload.get("intent"), transform=str.lower),
            priorities=_normalize_collection(payload.get("priority"), transform=str.upper),
            queues=_normalize_collection(payload.get("queue"), transform=str.lower),
            channels=_normalize_collection(payload.get("channel"), transform=str.lower),
        )

    def matches(self, *, ticket: Ticket) -> bool:
        return (
            _matches(self.intents, ticket.intent.lower())
            and _matches(self.priorities, ticket.priority.upper())
            and _matches(self.queues, ticket.queue.lower())
            and _matches(self.channels, ticket.channel.lower())
        )


@dataclass(frozen=True)
class SlaRule:
    rule_id: str
    first_response_minutes: int
    resolution_minutes: int
    escalation_target: str
    escalate_on_breaches: tuple[str, ...]
    scope: MatchScope


@dataclass(frozen=True)
class SlaCheckResult:
    first_response_due_at: datetime
    resolution_due_at: datetime
    breached_items: list[str]
    escalation_targets: list[str]
    policy_version: str
    matched_rule_id: str
    matched_rule_path: str
    used_fallback: bool


class SlaEngine:
    def __init__(
        self,
        *,
        policy_version: str,
        fallback_rule: SlaRule,
        override_rules: Sequence[SlaRule],
    ) -> None:
        self._policy_version = policy_version
        self._fallback_rule = fallback_rule
        self._override_rules = tuple(override_rules)

    @classmethod
    def from_file(cls, path: Path) -> SlaEngine:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            return cls.default_policy()

        if isinstance(payload.get("rules"), Mapping) and "overrides" not in payload:
            return cls._from_legacy_payload(payload)

        fallback_rule = cls._parse_rule(
            rule_id="fallback",
            raw=payload.get("fallback"),
            scope=MatchScope.any(),
        )
        overrides: list[SlaRule] = []
        for idx, item in enumerate(payload.get("overrides", [])):
            if not isinstance(item, Mapping):
                continue
            rule_id = str(item.get("id") or f"override-{idx}")
            overrides.append(
                cls._parse_rule(
                    rule_id=rule_id,
                    raw=item,
                    scope=MatchScope.from_payload(item.get("when")),
                )
            )

        return cls(
            policy_version=str(payload.get("version") or "sla-policy-v1"),
            fallback_rule=fallback_rule,
            override_rules=overrides,
        )

    @classmethod
    def default_policy(cls) -> SlaEngine:
        return cls(
            policy_version="sla-policy-default",
            fallback_rule=cls._default_rule("fallback"),
            override_rules=(),
        )

    @classmethod
    def _from_legacy_payload(cls, payload: Mapping[str, object]) -> SlaEngine:
        rules_data = payload.get("rules")
        if not isinstance(rules_data, Mapping):
            return cls.default_policy()

        overrides: list[SlaRule] = []
        for priority, item in rules_data.items():
            if not isinstance(item, Mapping):
                continue
            rule_id = f"legacy-{str(priority).upper()}"
            scope = MatchScope(
                intents=frozenset(),
                priorities=frozenset({str(priority).upper()}),
                queues=frozenset(),
                channels=frozenset(),
            )
            overrides.append(cls._parse_rule(rule_id=rule_id, raw=item, scope=scope))

        fallback_rule = next(
            (rule for rule in overrides if "P3" in rule.scope.priorities),
            cls._default_rule("fallback"),
        )
        return cls(
            policy_version=str(payload.get("version") or "legacy-sla-v1"),
            fallback_rule=fallback_rule,
            override_rules=overrides,
        )

    @classmethod
    def _parse_rule(cls, *, rule_id: str, raw: object, scope: MatchScope) -> SlaRule:
        if not isinstance(raw, Mapping):
            return cls._default_rule(rule_id, scope=scope)

        first_response_minutes = _safe_int(
            raw.get("first_response_minutes"),
            default=_DEFAULT_FIRST_RESPONSE_MINUTES,
        )
        resolution_minutes = _safe_int(
            raw.get("resolution_minutes"),
            default=_DEFAULT_RESOLUTION_MINUTES,
        )
        escalation_target = str(
            raw.get("escalation_target") or raw.get("escalation") or _DEFAULT_ESCALATION_TARGET
        )
        escalate_on_breaches = _parse_breach_targets(raw.get("escalate_on_breaches"))
        return SlaRule(
            rule_id=rule_id,
            first_response_minutes=first_response_minutes,
            resolution_minutes=resolution_minutes,
            escalation_target=escalation_target,
            escalate_on_breaches=escalate_on_breaches,
            scope=scope,
        )

    @classmethod
    def _default_rule(cls, rule_id: str, *, scope: MatchScope | None = None) -> SlaRule:
        return SlaRule(
            rule_id=rule_id,
            first_response_minutes=_DEFAULT_FIRST_RESPONSE_MINUTES,
            resolution_minutes=_DEFAULT_RESOLUTION_MINUTES,
            escalation_target=_DEFAULT_ESCALATION_TARGET,
            escalate_on_breaches=_DEFAULT_ESCALATE_ON_BREACHES,
            scope=scope or MatchScope.any(),
        )

    def evaluate(
        self,
        ticket: Ticket,
        events: list[TicketEvent],
        *,
        now: datetime | None = None,
    ) -> SlaCheckResult:
        reference_now = now or datetime.now(UTC)
        rule, matched_rule_path, used_fallback = self._select_rule(ticket)

        created_at = ticket.created_at or reference_now
        first_due = created_at + timedelta(minutes=rule.first_response_minutes)
        resolution_due = created_at + timedelta(minutes=rule.resolution_minutes)

        first_response_done = any(
            event.event_type in _FIRST_RESPONSE_EVENT_TYPES for event in events
        )
        resolved = ticket.status in {"resolved", "closed"}

        breaches: list[str] = []
        if not first_response_done and reference_now > first_due:
            breaches.append("first_response_overdue")
        if not resolved and reference_now > resolution_due:
            breaches.append("resolution_overdue")

        escalation_targets: list[str] = []
        if breaches and rule.escalation_target:
            for breach in breaches:
                target_missing = rule.escalation_target not in escalation_targets
                if breach in rule.escalate_on_breaches and target_missing:
                    escalation_targets.append(rule.escalation_target)

        return SlaCheckResult(
            first_response_due_at=first_due,
            resolution_due_at=resolution_due,
            breached_items=breaches,
            escalation_targets=escalation_targets,
            policy_version=self._policy_version,
            matched_rule_id=rule.rule_id,
            matched_rule_path=matched_rule_path,
            used_fallback=used_fallback,
        )

    def _select_rule(self, ticket: Ticket) -> tuple[SlaRule, str, bool]:
        for idx, rule in enumerate(self._override_rules):
            if rule.scope.matches(ticket=ticket):
                return rule, f"sla.overrides[{idx}]::{rule.rule_id}", False
        return self._fallback_rule, f"sla.fallback::{self._fallback_rule.rule_id}", True


def _normalize_collection(
    raw: object,
    *,
    transform: Callable[[str], str],
) -> frozenset[str]:
    if raw is None:
        return frozenset()

    values: list[str] = []
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        values = [str(item) for item in raw]
    else:
        values = [str(raw)]

    normalized = {transform(item.strip()) for item in values if item and item.strip()}
    return frozenset(normalized)


def _matches(selector: frozenset[str], value: str) -> bool:
    if not selector or "*" in selector:
        return True
    return value in selector


def _safe_int(raw: object, *, default: int) -> int:
    if isinstance(raw, int):
        return max(1, raw)
    if isinstance(raw, float):
        return max(1, int(raw))
    if isinstance(raw, str):
        try:
            return max(1, int(raw))
        except ValueError:
            return default

    try:
        return max(1, int(str(raw)))
    except (TypeError, ValueError):
        return default


def _parse_breach_targets(raw: object) -> tuple[str, ...]:
    if raw is None:
        return _DEFAULT_ESCALATE_ON_BREACHES

    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        values = [str(item) for item in raw]
    else:
        return _DEFAULT_ESCALATE_ON_BREACHES

    deduped: list[str] = []
    for item in values:
        normalized = item.strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return tuple(deduped)
