from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.handoff_manager import HandoffManager
from core.intent_router import IntentDecision
from core.recommended_actions_engine import RecommendedActionsEngine
from core.sla_engine import SlaEngine
from core.summary_engine import SummaryEngine
from core.ticket_api import TicketAPI
from storage.ticket_repository import TicketRepository


def _build_api(tmp_path: Path) -> TicketAPI:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    return TicketAPI(repo)


def _default_policy_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "seed_data"
        / "sla_rules"
        / "default_sla_rules.json"
    )


def test_summary_handoff_and_sla_interop(tmp_path: Path) -> None:
    api = _build_api(tmp_path)

    ticket = api.create_ticket(
        channel="feishu",
        session_id="s-3",
        thread_id="th-3",
        title="严重投诉",
        latest_message="我要人工客服处理",
        intent="complaint",
        priority="P1",
        queue="support",
    )

    events = api.list_events(ticket.ticket_id)
    summary_engine = SummaryEngine()
    summary = summary_engine.case_summary(ticket, events)

    policy_path = _default_policy_path()
    sla_engine = SlaEngine.from_file(policy_path)
    sla_result = sla_engine.evaluate(ticket, events, now=datetime.now(UTC) + timedelta(hours=3))

    action_engine = RecommendedActionsEngine()
    actions = action_engine.recommend(
        ticket=ticket,
        intent=IntentDecision(
            intent="complaint", confidence=0.9, is_low_confidence=False, reason="test"
        ),
        retrieved_docs=[],
        sla_breaches=sla_result.breached_items,
    )

    decision = HandoffManager.from_file(policy_path).evaluate(
        ticket=ticket,
        intent=IntentDecision(
            intent="complaint", confidence=0.9, is_low_confidence=False, reason="test"
        ),
        case_summary=summary,
        recommendations=actions,
        recent_events=events,
        sla_result=sla_result,
    )

    assert sla_result.matched_rule_path.startswith("sla.overrides")
    assert "resolution_overdue" in sla_result.breached_items
    assert decision.should_handoff is True


def test_sla_first_response_timeout_and_complaint_escalation(tmp_path: Path) -> None:
    api = _build_api(tmp_path)
    ticket = api.create_ticket(
        channel="wecom",
        session_id="sla-first-response",
        thread_id="th-sla-first-response",
        title="投诉未处理",
        latest_message="我要投诉服务态度",
        intent="complaint",
        priority="P3",
        queue="support",
    )
    events = api.list_events(ticket.ticket_id)
    policy_path = _default_policy_path()

    sla_result = SlaEngine.from_file(policy_path).evaluate(
        ticket,
        events,
        now=(ticket.created_at or datetime.now(UTC)) + timedelta(minutes=30),
    )

    assert "first_response_overdue" in sla_result.breached_items
    assert "customer_relations" in sla_result.escalation_targets
    assert sla_result.matched_rule_id == "complaint-all"


def test_sla_resolution_timeout_after_first_response(tmp_path: Path) -> None:
    api = _build_api(tmp_path)
    ticket = api.create_ticket(
        channel="telegram",
        session_id="sla-resolution",
        thread_id="th-sla-resolution",
        title="设备故障",
        latest_message="设备反复掉线",
        intent="repair",
        priority="P2",
        queue="support",
    )
    api.assign_ticket(ticket.ticket_id, assignee="agent-1", actor_id="lead")
    updated_ticket = api.require_ticket(ticket.ticket_id)
    events = api.list_events(ticket.ticket_id)
    policy_path = _default_policy_path()

    sla_result = SlaEngine.from_file(policy_path).evaluate(
        updated_ticket,
        events,
        now=(updated_ticket.created_at or datetime.now(UTC)) + timedelta(hours=5),
    )

    assert "first_response_overdue" not in sla_result.breached_items
    assert "resolution_overdue" in sla_result.breached_items
    assert sla_result.escalation_targets == ["supervisor"]
    assert sla_result.matched_rule_id == "priority-p2"


def test_handoff_threshold_can_be_changed_by_policy_file(tmp_path: Path) -> None:
    policy_path = tmp_path / "custom_policy.json"
    payload = json.loads(_default_policy_path().read_text(encoding="utf-8"))
    payload["handoff"]["fallback_rules"] = [
        {
            "id": "custom-low-confidence",
            "reason": "custom-low-confidence",
            "trigger": "low_confidence",
            "low_confidence_threshold": 0.9,
        }
    ]
    payload["handoff"]["overrides"] = []
    policy_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    api = _build_api(tmp_path)
    ticket = api.create_ticket(
        channel="telegram",
        session_id="handoff-threshold",
        thread_id="th-handoff-threshold",
        title="一般咨询",
        latest_message="请问这个问题怎么处理",
        intent="other",
        priority="P4",
        queue="support",
    )
    events = api.list_events(ticket.ticket_id)
    decision = HandoffManager.from_file(policy_path).evaluate(
        ticket=ticket,
        intent=IntentDecision(
            intent="other",
            confidence=0.75,
            is_low_confidence=False,
            reason="test-threshold",
        ),
        case_summary="summary",
        recommendations=[],
        recent_events=events,
        sla_result=SlaEngine.from_file(policy_path).evaluate(ticket, events),
    )

    assert decision.should_handoff is True
    assert "custom-low-confidence" in decision.reason
    assert any(path.startswith("handoff.fallback_rules") for path in decision.matched_rule_paths)
