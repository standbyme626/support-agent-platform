from __future__ import annotations

from dataclasses import replace

from core.intent_router import IntentDecision
from core.recommended_actions_engine import RecommendedActionsEngine
from storage.models import KBDocument, Ticket


def _sample_ticket() -> Ticket:
    return Ticket(
        ticket_id="TCK-RA-1",
        channel="wecom",
        session_id="session-ra",
        thread_id="thread-ra",
        customer_id=None,
        title="投诉工单",
        latest_message="我要投诉并处理退款",
        intent="complaint",
        priority="P1",
        status="open",
        queue="support",
        assignee=None,
        needs_handoff=False,
    )


def test_recommended_actions_include_structured_fields_and_evidence() -> None:
    engine = RecommendedActionsEngine()
    actions = engine.recommend(
        ticket=_sample_ticket(),
        intent=IntentDecision(
            intent="complaint",
            confidence=0.4,
            is_low_confidence=True,
            reason="low confidence",
        ),
        retrieved_docs=[
            KBDocument(
                doc_id="HIS-1001",
                source_type="history_case",
                title="退款投诉历史案例",
                content="先核验支付单号再退款",
                tags=["退款", "投诉"],
                score=0.86,
            )
        ],
        sla_breaches=["resolution_overdue"],
    )

    assert actions
    assert all(0.0 <= action.confidence <= 1.0 for action in actions)
    assert all(action.evidence for action in actions)
    assert any(
        evidence.source_type == "history_case"
        for action in actions
        for evidence in action.evidence
    )
    assert all("evidence" in action.as_dict() for action in actions)


def test_recommended_actions_never_emit_without_evidence() -> None:
    engine = RecommendedActionsEngine()
    ticket = replace(_sample_ticket(), intent="other", priority="P4", title="一般咨询")
    actions = engine.recommend(
        ticket=ticket,
        intent=IntentDecision(
            intent="other",
            confidence=0.95,
            is_low_confidence=False,
            reason="high confidence",
        ),
        retrieved_docs=[],
        sla_breaches=[],
    )

    assert actions == []
