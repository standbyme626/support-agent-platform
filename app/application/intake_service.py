from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class IntakeService:
    """Application service for intake classification/session-control hints."""

    _FAQ_HINTS = ("how", "what", "guide", "faq", "help", "如何", "怎么", "怎样", "说明")
    _SUPPORT_HINTS = ("error", "failed", "issue", "broken", "fault", "故障", "异常", "报修")
    _SESSION_END_HINTS = ("/end", "结束当前对话", "结束会话", "先到这里", "结束这轮")
    _NEW_ISSUE_HINTS = ("/new", "新问题", "重新开始", "换个问题")

    def classify_intent(self, payload: dict[str, Any]) -> str:
        text = str(payload.get("text") or "").lower()
        if any(token in text for token in self._FAQ_HINTS):
            return "faq"
        if any(token in text for token in self._SUPPORT_HINTS):
            return "support"
        return "support"

    def run(self, session_id: str, message_text: str) -> dict[str, Any]:
        normalized = str(message_text or "").strip()
        lowered = normalized.lower()
        session_action: str | None = None
        if any(token in lowered for token in self._SESSION_END_HINTS):
            session_action = "session_end"
        elif any(token in lowered for token in self._NEW_ISSUE_HINTS):
            session_action = "new_issue"
        intent = self.classify_intent({"text": normalized})
        return {
            "status": "ok",
            "session_id": session_id,
            "intent": intent,
            "session_action": session_action,
            "message_text": normalized,
            "handled_at": datetime.now(UTC).isoformat(),
            "advice_only": True,
            "high_risk_action_executed": False,
        }
