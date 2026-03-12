from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from storage.models import Ticket, TicketEvent

from .intent_router import IntentDecision
from .recommended_actions_engine import RecommendedAction
from .sla_engine import SlaCheckResult
from .ticket_api import TicketAPI


@dataclass(frozen=True)
class HandoffDecision:
    should_handoff: bool
    reason: str
    payload: Mapping[str, object]
    policy_version: str = "legacy-handoff-v1"
    matched_rule_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleScope:
    intents: frozenset[str]
    priorities: frozenset[str]
    queues: frozenset[str]
    channels: frozenset[str]

    @classmethod
    def any(cls) -> RuleScope:
        return cls(
            intents=frozenset(),
            priorities=frozenset(),
            queues=frozenset(),
            channels=frozenset(),
        )

    @classmethod
    def from_payload(cls, payload: object) -> RuleScope:
        if not isinstance(payload, Mapping):
            return cls.any()
        return cls(
            intents=_parse_selector(payload.get("intent"), transform=str.lower),
            priorities=_parse_selector(payload.get("priority"), transform=str.upper),
            queues=_parse_selector(payload.get("queue"), transform=str.lower),
            channels=_parse_selector(payload.get("channel"), transform=str.lower),
        )

    def matches(self, *, ticket: Ticket) -> bool:
        return (
            _selector_matches(self.intents, ticket.intent.lower())
            and _selector_matches(self.priorities, ticket.priority.upper())
            and _selector_matches(self.queues, ticket.queue.lower())
            and _selector_matches(self.channels, ticket.channel.lower())
        )


@dataclass(frozen=True)
class HandoffRule:
    rule_id: str
    reason: str
    trigger: str
    scope: RuleScope
    low_confidence_threshold: float | None = None
    keywords: tuple[str, ...] = ()
    sla_breaches: tuple[str, ...] = ()


class HandoffManager:
    """Human handoff policies for complex/high-risk cases."""

    def __init__(
        self,
        *,
        policy_version: str = "handoff-policy-default",
        fallback_rules: Sequence[HandoffRule] | None = None,
        override_rules: Sequence[HandoffRule] | None = None,
    ) -> None:
        if fallback_rules is None and override_rules is None:
            override_rules, fallback_rules = self._legacy_rules()
            self._policy_version = (
                "legacy-handoff-v1"
                if policy_version == "handoff-policy-default"
                else policy_version
            )
        else:
            self._policy_version = policy_version
            fallback_rules = fallback_rules or ()
            override_rules = override_rules or ()

        self._fallback_rules = tuple(fallback_rules)
        self._override_rules = tuple(override_rules)

    @classmethod
    def from_file(cls, path: Path) -> HandoffManager:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            return cls()

        section = payload.get("handoff")
        if not isinstance(section, Mapping):
            return cls(policy_version=str(payload.get("version") or "legacy-handoff-v1"))

        fallback_rules = cls._parse_rules(section.get("fallback_rules"))
        if not fallback_rules and isinstance(section.get("fallback"), Mapping):
            fallback_rules = cls._parse_rules(section["fallback"].get("rules"))
        override_rules = cls._parse_rules(section.get("overrides"))

        if not fallback_rules and not override_rules:
            return cls(policy_version=str(section.get("version") or payload.get("version") or "v1"))

        resolved_version = str(
            section.get("version") or payload.get("version") or "handoff-policy-v1"
        )
        return cls(
            policy_version=resolved_version,
            fallback_rules=fallback_rules,
            override_rules=override_rules,
        )

    def evaluate(
        self,
        *,
        ticket: Ticket,
        intent: IntentDecision,
        case_summary: str,
        recommendations: list[RecommendedAction],
        recent_events: list[TicketEvent],
        sla_result: SlaCheckResult | None = None,
    ) -> HandoffDecision:
        reasons: list[str] = []
        matched_rule_paths: list[str] = []
        sla_breaches = set(sla_result.breached_items if sla_result else [])

        for idx, rule in enumerate(self._override_rules):
            if not rule.scope.matches(ticket=ticket):
                continue
            triggered = self._rule_triggered(
                rule,
                ticket=ticket,
                intent=intent,
                sla_breaches=sla_breaches,
            )
            if not triggered:
                continue
            reasons.append(rule.reason)
            matched_rule_paths.append(f"handoff.overrides[{idx}]::{rule.rule_id}")

        for idx, rule in enumerate(self._fallback_rules):
            if not rule.scope.matches(ticket=ticket):
                continue
            triggered = self._rule_triggered(
                rule,
                ticket=ticket,
                intent=intent,
                sla_breaches=sla_breaches,
            )
            if not triggered:
                continue
            reasons.append(rule.reason)
            matched_rule_paths.append(f"handoff.fallback_rules[{idx}]::{rule.rule_id}")

        deduped_reasons: list[str] = []
        for item in reasons:
            if item not in deduped_reasons:
                deduped_reasons.append(item)

        should_handoff = len(deduped_reasons) > 0
        payload = {
            "ticket_id": ticket.ticket_id,
            "summary": case_summary,
            "evidence_events": [event.event_type for event in recent_events[-5:]],
            "recommended_actions": [action.action for action in recommendations],
            "policy_version": self._policy_version,
            "matched_rule_paths": matched_rule_paths,
            "sla_breaches": sorted(sla_breaches),
        }

        if not should_handoff:
            return HandoffDecision(
                False,
                "no-trigger",
                payload,
                policy_version=self._policy_version,
                matched_rule_paths=tuple(matched_rule_paths),
            )

        return HandoffDecision(
            True,
            ";".join(deduped_reasons),
            payload,
            policy_version=self._policy_version,
            matched_rule_paths=tuple(matched_rule_paths),
        )

    def mark_handoff(
        self, ticket_api: TicketAPI, ticket_id: str, decision: HandoffDecision
    ) -> Ticket:
        ticket = ticket_api.update_ticket(
            ticket_id,
            {
                "status": "handoff",
                "needs_handoff": True,
                "queue": "human-handoff",
            },
            actor_id="handoff-manager",
        )
        ticket_api.add_event(
            ticket_id,
            event_type="handoff_triggered",
            actor_type="system",
            actor_id="handoff-manager",
            payload={"reason": decision.reason, "payload": decision.payload},
        )
        return ticket

    def resume(
        self,
        ticket_api: TicketAPI,
        ticket_id: str,
        *,
        actor_id: str,
        note: str,
        approval_id: str | None = None,
        context: Mapping[str, object] | None = None,
    ) -> Ticket:
        payload_context = dict(context or {})
        resume_state = str(payload_context.get("resume_handoff_state") or "").strip()
        ticket = ticket_api.update_ticket(
            ticket_id,
            {
                "status": "pending",
                "needs_handoff": False,
                "latest_message": note,
                "handoff_state": resume_state or "accepted",
            },
            actor_id=actor_id,
        )
        ticket_api.add_event(
            ticket_id,
            event_type="handoff_resumed",
            actor_type="agent",
            actor_id=actor_id,
            payload={
                "note": note,
                "approval_id": approval_id,
                "context": payload_context,
            },
        )
        return ticket

    @staticmethod
    def _rule_triggered(
        rule: HandoffRule,
        *,
        ticket: Ticket,
        intent: IntentDecision,
        sla_breaches: set[str],
    ) -> bool:
        trigger = rule.trigger
        if trigger == "always":
            return True
        if trigger == "low_confidence":
            threshold = (
                rule.low_confidence_threshold if rule.low_confidence_threshold is not None else 0.45
            )
            return intent.is_low_confidence or intent.confidence < threshold
        if trigger == "customer_request_human":
            normalized_message = ticket.latest_message.lower()
            keywords = rule.keywords or ("人工", "客服", "human", "agent")
            return any(keyword in normalized_message for keyword in keywords)
        if trigger == "sla_breach":
            if not sla_breaches:
                return False
            if not rule.sla_breaches:
                return True
            return bool(set(rule.sla_breaches).intersection(sla_breaches))
        return False

    @classmethod
    def _parse_rules(cls, raw: object) -> list[HandoffRule]:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return []

        rules: list[HandoffRule] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, Mapping):
                continue
            rule_id = str(item.get("id") or f"rule-{idx}")
            reason = str(item.get("reason") or rule_id)
            trigger = str(item.get("trigger") or "always").strip().lower()
            rules.append(
                HandoffRule(
                    rule_id=rule_id,
                    reason=reason,
                    trigger=trigger,
                    scope=RuleScope.from_payload(item.get("when")),
                    low_confidence_threshold=_safe_float(item.get("low_confidence_threshold")),
                    keywords=tuple(_parse_keyword_list(item.get("keywords"))),
                    sla_breaches=tuple(_parse_text_list(item.get("sla_breaches"))),
                )
            )
        return rules

    @staticmethod
    def _legacy_rules() -> tuple[tuple[HandoffRule, ...], tuple[HandoffRule, ...]]:
        return (
            (
                HandoffRule(
                    rule_id="legacy-priority-p1",
                    reason="priority-P1",
                    trigger="always",
                    scope=RuleScope(
                        intents=frozenset(),
                        priorities=frozenset({"P1"}),
                        queues=frozenset(),
                        channels=frozenset(),
                    ),
                ),
                HandoffRule(
                    rule_id="legacy-complaint-intent",
                    reason="complaint-intent",
                    trigger="always",
                    scope=RuleScope(
                        intents=frozenset({"complaint"}),
                        priorities=frozenset(),
                        queues=frozenset(),
                        channels=frozenset(),
                    ),
                ),
            ),
            (
                HandoffRule(
                    rule_id="legacy-low-confidence",
                    reason="low-confidence",
                    trigger="low_confidence",
                    scope=RuleScope.any(),
                    low_confidence_threshold=0.45,
                ),
                HandoffRule(
                    rule_id="legacy-customer-asks-human",
                    reason="customer-asks-human",
                    trigger="customer_request_human",
                    scope=RuleScope.any(),
                    keywords=("人工", "客服", "human", "agent"),
                ),
            ),
        )


def _parse_selector(raw: object, *, transform: Callable[[str], str]) -> frozenset[str]:
    values = _parse_text_list(raw)
    return frozenset(transform(item) for item in values)


def _selector_matches(selector: frozenset[str], value: str) -> bool:
    if not selector or "*" in selector:
        return True
    return value in selector


def _parse_text_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        candidate = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        candidate = [str(item) for item in raw]
    else:
        candidate = [str(raw)]

    values: list[str] = []
    for item in candidate:
        normalized = item.strip()
        if normalized:
            values.append(normalized)
    return values


def _parse_keyword_list(raw: object) -> list[str]:
    return [item.lower() for item in _parse_text_list(raw)]


def _safe_float(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return None

    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None
