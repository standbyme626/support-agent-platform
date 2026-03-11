from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    is_low_confidence: bool
    reason: str


class IntentRouter:
    """Rule-based intent router with threshold and low-confidence fallback."""

    _intent_keywords: ClassVar[dict[str, set[str]]] = {
        "greeting": {"你好", "您好", "hello", "hey", "在吗"},
        "faq": {"怎么", "如何", "查询", "帮助", "help", "faq"},
        "repair": {"报修", "故障", "坏了", "维修", "中断"},
        "complaint": {"投诉", "差评", "生气", "不满意", "赔偿"},
        "billing": {"费用", "扣费", "账单", "发票", "退款", "支付"},
        "other": set(),
    }

    def __init__(self, threshold: float = 0.58, low_confidence_fallback: str = "other") -> None:
        self._threshold = threshold
        self._fallback = low_confidence_fallback

    def route(self, message: str) -> IntentDecision:
        normalized = message.lower().strip()
        if not normalized:
            return IntentDecision(
                intent=self._fallback,
                confidence=0.0,
                is_low_confidence=True,
                reason="empty-message",
            )

        scored = [
            (intent, self._score_intent(normalized, keywords))
            for intent, keywords in self._intent_keywords.items()
            if intent != "other"
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        best_intent, best_score = scored[0] if scored else (self._fallback, 0.0)

        confidence = min(1.0, best_score)
        if confidence < self._threshold:
            return IntentDecision(
                intent=self._fallback,
                confidence=confidence,
                is_low_confidence=True,
                reason=f"below-threshold:{self._threshold}",
            )

        return IntentDecision(
            intent=best_intent,
            confidence=confidence,
            is_low_confidence=False,
            reason="keyword-match",
        )

    @staticmethod
    def _score_intent(message: str, keywords: set[str]) -> float:
        if not keywords:
            return 0.0
        hits = sum(1 for word in keywords if word in message)
        if hits == 0:
            return 0.0
        # One strong keyword should cross the threshold for deterministic routing.
        return min(1.0, 0.65 + 0.2 * (hits - 1))
