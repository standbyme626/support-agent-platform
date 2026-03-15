from __future__ import annotations

from app.application.intake_service import IntakeService


def test_intake_service_classifies_intent_and_keeps_advice_only() -> None:
    service = IntakeService()

    faq_result = service.run("sess-001", "如何重置门禁权限？")
    assert faq_result["intent"] == "faq"
    assert faq_result["advice_only"] is True
    assert faq_result["high_risk_action_executed"] is False

    support_result = service.run("sess-001", "空调故障，完全不制冷")
    assert support_result["intent"] == "support"
    assert support_result["session_action"] is None


def test_intake_service_detects_session_controls() -> None:
    service = IntakeService()

    end_result = service.run("sess-002", "这轮先到这里，结束当前对话")
    assert end_result["session_action"] == "session_end"

    new_issue_result = service.run("sess-002", "/new 我有一个新问题")
    assert new_issue_result["session_action"] == "new_issue"
