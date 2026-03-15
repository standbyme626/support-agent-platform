from __future__ import annotations

from core.disambiguation import NewIssueDetector
from core.intent_router import IntentDecision
from storage.models import Ticket


def _intent(intent: str, *, low: bool = False) -> IntentDecision:
    return IntentDecision(
        intent=intent,
        confidence=0.35 if low else 0.9,
        is_low_confidence=low,
        reason="test",
    )


def _ticket(ticket_id: str, *, intent: str, latest_message: str) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        channel="wecom",
        session_id="sess-disambiguation-001",
        thread_id="thread-disambiguation-001",
        customer_id=None,
        title="test",
        latest_message=latest_message,
        intent=intent,
        priority="P2",
        status="pending",
        queue="support",
        assignee=None,
        needs_handoff=False,
    )


def test_new_issue_detector_prefers_new_issue_marker() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="另外一个新问题，电梯异响也要报修",
        intent=_intent("repair"),
        candidate_ticket_ids=["TCK-1002", "TCK-1001"],
        active_ticket_id="TCK-1002",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-1002", intent="repair", latest_message="停车场抬杆故障"),
    )

    assert result.decision == "new_issue_detected"
    assert result.reason == "chinese_new_issue_phrase"


def test_new_issue_detector_uses_clarification_for_low_confidence_multi_ticket() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="帮我看看",
        intent=_intent("other", low=True),
        candidate_ticket_ids=["TCK-2002", "TCK-2001"],
        active_ticket_id="TCK-2002",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-2002", intent="repair", latest_message="电梯异响"),
    )

    assert result.decision == "awaiting_disambiguation"
    assert result.suggested_ticket_id == "TCK-2002"


def test_new_issue_detector_keeps_progress_query_on_active_ticket() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="这个问题现在进度到哪了？",
        intent=_intent("progress_query"),
        candidate_ticket_ids=["TCK-3002", "TCK-3001"],
        active_ticket_id="TCK-3002",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-3002", intent="repair", latest_message="停车场抬杆故障"),
    )

    assert result.decision == "continue_current"
    assert result.suggested_ticket_id == "TCK-3002"
    assert result.reason == "progress_query_prefers_active"


def test_new_issue_detector_explicit_new_command_has_highest_priority() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="/new 继续当前问题",
        intent=_intent("repair"),
        candidate_ticket_ids=["TCK-4002", "TCK-4001"],
        active_ticket_id="TCK-4002",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-4002", intent="repair", latest_message="停车场抬杆故障"),
    )

    assert result.decision == "new_issue_detected"
    assert result.reason == "explicit_new_command"
    assert result.session_action == "new_issue"


def test_new_issue_detector_accepts_slash_new_with_whitespace() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="/ new 继续当前问题",
        intent=_intent("repair"),
        candidate_ticket_ids=["TCK-4012", "TCK-4011"],
        active_ticket_id="TCK-4012",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-4012", intent="repair", latest_message="停车场抬杆故障"),
    )

    assert result.decision == "new_issue_detected"
    assert result.reason == "explicit_new_command"
    assert result.session_action == "new_issue"


def test_new_issue_detector_accepts_wecom_mention_with_backslash_new_command() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="@智慧工单机器人 \\new 我有一个新问题",
        intent=_intent("repair"),
        candidate_ticket_ids=["TCK-4502", "TCK-4501"],
        active_ticket_id="TCK-4502",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-4502", intent="repair", latest_message="停车场抬杆故障"),
    )

    assert result.decision == "new_issue_detected"
    assert result.reason == "explicit_new_command"
    assert result.session_action == "new_issue"


def test_new_issue_detector_accepts_fullwidth_backslash_new_command() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="@智慧工单机器人 ＼new 我有一个新问题",
        intent=_intent("repair"),
        candidate_ticket_ids=["TCK-4602", "TCK-4601"],
        active_ticket_id="TCK-4602",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-4602", intent="repair", latest_message="停车场抬杆故障"),
    )

    assert result.decision == "new_issue_detected"
    assert result.reason == "explicit_new_command"
    assert result.session_action == "new_issue"


def test_new_issue_detector_end_phrase_requests_session_end() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="这轮先到这里，结束当前对话",
        intent=_intent("repair"),
        candidate_ticket_ids=["TCK-5002", "TCK-5001"],
        active_ticket_id="TCK-5002",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-5002", intent="repair", latest_message="电梯异响"),
    )

    assert result.decision == "continue_current"
    assert result.reason == "chinese_end_phrase"
    assert result.session_action == "session_end"


def test_new_issue_detector_accepts_slash_end_with_whitespace() -> None:
    detector = NewIssueDetector()
    result = detector.evaluate(
        message_text="/ end",
        intent=_intent("repair"),
        candidate_ticket_ids=["TCK-5102", "TCK-5101"],
        active_ticket_id="TCK-5102",
        requested_ticket_id=None,
        session_mode="multi_issue",
        last_intent="repair",
        active_ticket=_ticket("TCK-5102", intent="repair", latest_message="电梯异响"),
    )

    assert result.decision == "continue_current"
    assert result.reason == "explicit_end_command"
    assert result.session_action == "session_end"
