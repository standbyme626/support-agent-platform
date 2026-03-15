from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Literal

from storage.models import Ticket

from .intent_router import IntentDecision

DisambiguationDecision = Literal[
    "continue_current",
    "new_issue_detected",
    "awaiting_disambiguation",
]
SessionControlAction = Literal[
    "session_end",
    "new_issue",
    "continue_current",
    "pause_session",
    "resume_session",
    "transfer_to_agent",
    "view_history",
    "reopen_ticket",
    "list_tickets",
    "view_ticket_detail",
]
SessionControlSource = Literal["explicit_command", "chinese_rule"]

_EXPLICIT_COMMAND_RE = re.compile(
    r"^\s*(?:[@＠][^\s]+[:：,，]?\s*)*(?:\\|/|／|＼)\s*(?P<command>end|new|pause|resume|transfer|history|reopen|list)\b",
    re.IGNORECASE,
)
_END_RULE_PHRASES = (
    "结束当前对话",
    "结束当前会话",
    "结束对话",
    "结束会话",
    "这轮先到这里",
    "先到这里",
    "结束",
    "关闭对话",
    "关闭会话",
)
_NEW_RULE_PHRASES = (
    "我有一个新问题",
    "重新开始",
    "重新开一个",
    "新问题",
    "另一个问题",
    "另外一个问题",
    "新建工单",
    "开新工单",
    "新建问题",
    "新开工单",
    "新创建工单",
    "创建一个工单",
    "开一个新工单",
    "新建一个工单",
    "创建工单",
    "开一个工单",
)
_CONTINUE_RULE_PHRASES = (
    "继续当前",
    "继续这个",
    "继续这个问题",
    "继续当前工单",
    "继续看一下工单",
    "还是这个问题",
)
_PAUSE_RULE_PHRASES = (
    "暂停会话",
    "暂时结束",
    "先暂停",
    "等一下",
    "暂停",
    "暂时",
)
_RESUME_RULE_PHRASES = (
    "恢复会话",
    "继续会话",
    "继续刚才的",
    "回来",
    "继续",
)
_TRANSFER_RULE_PHRASES = (
    "转人工",
    "人工服务",
    "需要人工",
    "转接人工",
    "找人工",
)
_HISTORY_RULE_PHRASES = (
    "查看历史",
    "之前的问题",
    "历史记录",
    "之前那个",
)
_REOPEN_RULE_PHRASES = (
    "重新打开",
    "重开工单",
    "重新开启",
    "再开一下",
)
_LIST_TICKETS_PHRASES = (
    "查看工单列表",
    "查看所有工单",
    "查看我的工单列表",
    "我的工单列表",
    "工单列表",
    "有哪些工单",
    "查看P1工单",
    "查看P2工单",
    "查看P3工单",
    "查看P4工单",
    "查看紧急工单",
    "查看高优先级工单",
    "查看低优先级工单",
    "待处理工单列表",
    "处理中工单列表",
    "已完结工单列表",
    "我的工单",
    "查看工单",
)
_VIEW_TICKET_PHRASES = (
    "查看详情",
    "查看工单详情",
    "工单详情",
    "查看这个工单",
    "这个工单怎么样",
    "工单现在怎样",
    "这个工单进度",
)


@dataclass(frozen=True)
class SessionControlMatch:
    action: SessionControlAction
    source: SessionControlSource
    priority: int
    reason: str
    confidence: float


def detect_session_control(message_text: str) -> SessionControlMatch | None:
    text = str(message_text or "").strip()
    if not text:
        return None

    command_match = _EXPLICIT_COMMAND_RE.match(text)
    if command_match is not None:
        command = str(command_match.group("command") or "").lower()
        if command == "end":
            return SessionControlMatch(
                action="session_end",
                source="explicit_command",
                priority=1,
                reason="explicit_end_command",
                confidence=1.0,
            )
        if command == "new":
            return SessionControlMatch(
                action="new_issue",
                source="explicit_command",
                priority=1,
                reason="explicit_new_command",
                confidence=1.0,
            )
        if command == "pause":
            return SessionControlMatch(
                action="pause_session",
                source="explicit_command",
                priority=1,
                reason="explicit_pause_command",
                confidence=1.0,
            )
        if command == "resume":
            return SessionControlMatch(
                action="resume_session",
                source="explicit_command",
                priority=1,
                reason="explicit_resume_command",
                confidence=1.0,
            )
        if command == "transfer":
            return SessionControlMatch(
                action="transfer_to_agent",
                source="explicit_command",
                priority=1,
                reason="explicit_transfer_command",
                confidence=1.0,
            )
        if command == "history":
            return SessionControlMatch(
                action="view_history",
                source="explicit_command",
                priority=1,
                reason="explicit_history_command",
                confidence=1.0,
            )
        if command == "reopen":
            return SessionControlMatch(
                action="reopen_ticket",
                source="explicit_command",
                priority=1,
                reason="explicit_reopen_command",
                confidence=1.0,
            )
        if command == "list":
            return SessionControlMatch(
                action="list_tickets",
                source="explicit_command",
                priority=1,
                reason="explicit_list_command",
                confidence=1.0,
            )

    lowered = text.lower()
    if any(phrase in text for phrase in _END_RULE_PHRASES):
        return SessionControlMatch(
            action="session_end",
            source="chinese_rule",
            priority=2,
            reason="chinese_end_phrase",
            confidence=0.95,
        )
    if any(phrase in text for phrase in _NEW_RULE_PHRASES):
        return SessionControlMatch(
            action="new_issue",
            source="chinese_rule",
            priority=2,
            reason="chinese_new_issue_phrase",
            confidence=0.95,
        )
    if any(phrase in text for phrase in _CONTINUE_RULE_PHRASES):
        return SessionControlMatch(
            action="continue_current",
            source="chinese_rule",
            priority=2,
            reason="chinese_continue_phrase",
            confidence=0.88,
        )
    if any(phrase in text for phrase in _PAUSE_RULE_PHRASES):
        return SessionControlMatch(
            action="pause_session",
            source="chinese_rule",
            priority=2,
            reason="chinese_pause_phrase",
            confidence=0.90,
        )
    if any(phrase in text for phrase in _RESUME_RULE_PHRASES):
        return SessionControlMatch(
            action="resume_session",
            source="chinese_rule",
            priority=2,
            reason="chinese_resume_phrase",
            confidence=0.90,
        )
    if any(phrase in text for phrase in _TRANSFER_RULE_PHRASES):
        return SessionControlMatch(
            action="transfer_to_agent",
            source="chinese_rule",
            priority=2,
            reason="chinese_transfer_phrase",
            confidence=0.95,
        )
    if any(phrase in text for phrase in _HISTORY_RULE_PHRASES):
        return SessionControlMatch(
            action="view_history",
            source="chinese_rule",
            priority=2,
            reason="chinese_history_phrase",
            confidence=0.85,
        )
    if any(phrase in text for phrase in _REOPEN_RULE_PHRASES):
        return SessionControlMatch(
            action="reopen_ticket",
            source="chinese_rule",
            priority=2,
            reason="chinese_reopen_phrase",
            confidence=0.90,
        )

    if "keep current" in lowered:
        return SessionControlMatch(
            action="continue_current",
            source="chinese_rule",
            priority=2,
            reason="english_continue_phrase",
            confidence=0.85,
        )
    if any(phrase in text for phrase in _LIST_TICKETS_PHRASES):
        return SessionControlMatch(
            action="list_tickets",
            source="chinese_rule",
            priority=2,
            reason="chinese_list_tickets_phrase",
            confidence=0.90,
        )
    if any(phrase in text for phrase in _VIEW_TICKET_PHRASES):
        return SessionControlMatch(
            action="view_ticket_detail",
            source="chinese_rule",
            priority=2,
            reason="chinese_view_ticket_phrase",
            confidence=0.90,
        )
    return None


@dataclass(frozen=True)
class DisambiguationResult:
    decision: DisambiguationDecision
    confidence: float
    reason: str
    intent: IntentDecision
    suggested_ticket_id: str | None
    candidate_ticket_ids: tuple[str, ...]
    active_ticket_id: str | None
    session_action: SessionControlAction | None = None


class NewIssueDetector:
    """Rule-based detector for multi-ticket disambiguation and new issue hints."""

    _TICKET_ID_PATTERN = re.compile(r"\b(?:TCK-[A-Za-z0-9_-]+|TICKET-[A-Za-z0-9_-]+)\b")
    _PROGRESS_KEYWORDS = ("进度", "跟进", "到哪", "状态", "处理到哪", "什么时候", "查询工单")
    _NEW_ISSUE_MARKERS = (
        "新问题",
        "另一个",
        "另外一个",
        "另外",
        "还有一个",
        "再报",
        "重新报",
        "another",
        "also",
    )
    _CONTINUE_MARKERS = (
        "这个问题",
        "这个工单",
        "继续",
        "还是这个",
        "上次",
        "刚才",
        "当前工单",
        "继续当前",
        "同一个",
    )
    _SERVICE_INTENTS: ClassVar[set[str]] = {"repair", "complaint", "billing"}

    def evaluate(
        self,
        *,
        message_text: str,
        intent: IntentDecision,
        candidate_ticket_ids: list[str],
        active_ticket_id: str | None,
        requested_ticket_id: str | None,
        session_mode: str | None,
        last_intent: str | None,
        active_ticket: Ticket | None = None,
    ) -> DisambiguationResult:
        normalized_candidates = self._dedupe_ticket_ids(candidate_ticket_ids)
        normalized_active = str(active_ticket_id or "").strip() or None
        normalized_requested = str(requested_ticket_id or "").strip() or None
        normalized_mode = str(session_mode or "").strip() or None

        if normalized_active is None and normalized_candidates:
            normalized_active = normalized_candidates[0]

        text = str(message_text or "").strip()
        lowered = text.lower()
        explicit_ticket = self._extract_ticket_id(text)
        session_control = detect_session_control(text)

        if session_control is not None:
            if session_control.action == "session_end":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="session_end",
                )

            if session_control.action == "new_issue":
                return self._build_result(
                    decision="new_issue_detected",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=None,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="new_issue",
                )

            if session_control.action == "continue_current":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="continue_current",
                )

            if session_control.action == "pause_session":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="pause_session",
                )

            if session_control.action == "resume_session":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="resume_session",
                )

            if session_control.action == "transfer_to_agent":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="transfer_to_agent",
                )

            if session_control.action == "view_history":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="view_history",
                )

            if session_control.action == "reopen_ticket":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="reopen_ticket",
                )

            if session_control.action == "list_tickets":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=None,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="list_tickets",
                )

            if session_control.action == "view_ticket_detail":
                return self._build_result(
                    decision="continue_current",
                    confidence=session_control.confidence,
                    reason=session_control.reason,
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action="view_ticket_detail",
                )

        if normalized_requested:
            return self._build_result(
                decision="continue_current",
                confidence=0.99,
                reason="requested_ticket_id",
                intent=intent,
                suggested_ticket_id=normalized_requested,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        if explicit_ticket and explicit_ticket in normalized_candidates:
            return self._build_result(
                decision="continue_current",
                confidence=0.99,
                reason="explicit_ticket_in_message",
                intent=intent,
                suggested_ticket_id=explicit_ticket,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        if self._looks_like_progress_query(text) and normalized_active:
            return self._build_result(
                decision="continue_current",
                confidence=0.96,
                reason="progress_query_prefers_active",
                intent=intent,
                suggested_ticket_id=normalized_active,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        if not normalized_candidates:
            return self._build_result(
                decision="continue_current",
                confidence=0.80,
                reason="no_ticket_candidates",
                intent=intent,
                suggested_ticket_id=None,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        has_new_marker = any(marker in lowered for marker in self._NEW_ISSUE_MARKERS)
        has_continue_marker = any(marker in lowered for marker in self._CONTINUE_MARKERS)

        if normalized_mode == "awaiting_new_issue" and not has_continue_marker:
            return self._build_result(
                decision="new_issue_detected",
                confidence=0.90,
                reason="session_mode_awaiting_new_issue",
                intent=intent,
                suggested_ticket_id=None,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        if has_new_marker and not has_continue_marker:
            return self._build_result(
                decision="new_issue_detected",
                confidence=0.89,
                reason="new_issue_marker",
                intent=intent,
                suggested_ticket_id=None,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        if has_continue_marker and normalized_active:
            return self._build_result(
                decision="continue_current",
                confidence=0.85,
                reason="continue_marker",
                intent=intent,
                suggested_ticket_id=normalized_active,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        if active_ticket is not None:
            reference_intent = str(active_ticket.intent or "").strip()
        else:
            reference_intent = str(last_intent or "").strip()
        intent_shift = (
            bool(reference_intent)
            and intent.intent in self._SERVICE_INTENTS
            and reference_intent in self._SERVICE_INTENTS
            and intent.intent != reference_intent
        )

        similarity = 0.0
        if active_ticket is not None:
            similarity = self._char_similarity(text, str(active_ticket.latest_message or ""))

        if len(normalized_candidates) > 1:
            if normalized_mode == "awaiting_disambiguation":
                return self._build_result(
                    decision="awaiting_disambiguation",
                    confidence=0.75,
                    reason="session_mode_awaiting_disambiguation",
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action=None,
                )

            if intent.is_low_confidence:
                return self._build_result(
                    decision="awaiting_disambiguation",
                    confidence=0.66,
                    reason="low_confidence_with_multi_tickets",
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action=None,
                )

            if intent_shift and similarity <= 0.18:
                return self._build_result(
                    decision="new_issue_detected",
                    confidence=0.78,
                    reason="intent_shift_low_similarity",
                    intent=intent,
                    suggested_ticket_id=None,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action=None,
                )

            if intent_shift or (0.0 < similarity < 0.35):
                return self._build_result(
                    decision="awaiting_disambiguation",
                    confidence=0.62,
                    reason="multi_ticket_uncertain",
                    intent=intent,
                    suggested_ticket_id=normalized_active,
                    candidate_ticket_ids=normalized_candidates,
                    active_ticket_id=normalized_active,
                    session_action=None,
                )

        if intent_shift and similarity <= 0.18:
            return self._build_result(
                decision="new_issue_detected",
                confidence=0.74,
                reason="single_ticket_intent_shift",
                intent=intent,
                suggested_ticket_id=None,
                candidate_ticket_ids=normalized_candidates,
                active_ticket_id=normalized_active,
                session_action=None,
            )

        return self._build_result(
            decision="continue_current",
            confidence=0.72,
            reason="default_continue",
            intent=intent,
            suggested_ticket_id=normalized_active,
            candidate_ticket_ids=normalized_candidates,
            active_ticket_id=normalized_active,
            session_action=None,
        )

    @classmethod
    def _build_result(
        cls,
        *,
        decision: DisambiguationDecision,
        confidence: float,
        reason: str,
        intent: IntentDecision,
        suggested_ticket_id: str | None,
        candidate_ticket_ids: list[str],
        active_ticket_id: str | None,
        session_action: SessionControlAction | None = None,
    ) -> DisambiguationResult:
        return DisambiguationResult(
            decision=decision,
            confidence=max(0.0, min(confidence, 1.0)),
            reason=reason,
            intent=intent,
            suggested_ticket_id=str(suggested_ticket_id).strip() if suggested_ticket_id else None,
            candidate_ticket_ids=tuple(candidate_ticket_ids),
            active_ticket_id=str(active_ticket_id).strip() if active_ticket_id else None,
            session_action=session_action,
        )

    @classmethod
    def _extract_ticket_id(cls, message_text: str) -> str | None:
        match = cls._TICKET_ID_PATTERN.search(message_text)
        if match is None:
            return None
        return str(match.group(0)).strip() or None

    @classmethod
    def _looks_like_progress_query(cls, message_text: str) -> bool:
        text = str(message_text or "").strip()
        if not text:
            return False
        lowered = text.lower()
        if "progress" in lowered:
            return True
        return any(keyword in text for keyword in cls._PROGRESS_KEYWORDS)

    @staticmethod
    def _dedupe_ticket_ids(ticket_ids: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for raw_ticket_id in ticket_ids:
            ticket_id = str(raw_ticket_id).strip()
            if not ticket_id or ticket_id in seen:
                continue
            deduped.append(ticket_id)
            seen.add(ticket_id)
        return deduped

    @staticmethod
    def _char_similarity(left: str, right: str) -> float:
        left_chars = {ch for ch in left if ch.strip()}
        right_chars = {ch for ch in right if ch.strip()}
        if not left_chars or not right_chars:
            return 0.0
        intersection = left_chars.intersection(right_chars)
        union = left_chars.union(right_chars)
        if not union:
            return 0.0
        return len(intersection) / len(union)
