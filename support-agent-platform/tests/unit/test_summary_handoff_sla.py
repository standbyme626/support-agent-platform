from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.handoff_manager import HandoffManager
from core.intent_router import IntentDecision
from core.recommended_actions_engine import RecommendedActionsEngine
from core.sla_engine import SlaEngine
from core.summary_engine import SummaryEngine
from core.ticket_api import TicketAPI
from storage.ticket_repository import TicketRepository


def test_summary_handoff_and_sla_interop(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    api = TicketAPI(repo)

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

    sla_engine = SlaEngine.from_file(
        Path(__file__).resolve().parents[2] / "seed_data" / "sla_rules" / "default_sla_rules.json"
    )
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

    decision = HandoffManager().evaluate(
        ticket=ticket,
        intent=IntentDecision(
            intent="complaint", confidence=0.9, is_low_confidence=False, reason="test"
        ),
        case_summary=summary,
        recommendations=actions,
        recent_events=events,
    )

    assert "resolution_overdue" in sla_result.breached_items
    assert decision.should_handoff is True
