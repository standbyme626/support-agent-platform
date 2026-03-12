from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher

from storage.models import Ticket


@dataclass(frozen=True)
class DuplicateCandidate:
    ticket_id: str
    score: float
    reason: str
    signal_matches: tuple[str, ...]
    title: str
    status: str
    updated_at: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "ticket_id": self.ticket_id,
            "score": round(self.score, 4),
            "reason": self.reason,
            "signal_matches": list(self.signal_matches),
            "title": self.title,
            "status": self.status,
            "updated_at": self.updated_at,
        }


class DuplicateDetector:
    _TOKEN_RE = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff]+")

    def __init__(self, *, score_threshold: float = 0.58, max_candidates: int = 5) -> None:
        self._score_threshold = score_threshold
        self._max_candidates = max_candidates

    def detect(self, ticket: Ticket, pool: list[Ticket]) -> list[DuplicateCandidate]:
        ranked: list[DuplicateCandidate] = []
        for item in pool:
            if item.ticket_id == ticket.ticket_id:
                continue
            if item.status == "closed":
                continue
            score, signals = self._score(ticket, item)
            if score < self._score_threshold:
                continue
            reason = ", ".join(signals[:3]) if signals else "text_similarity"
            ranked.append(
                DuplicateCandidate(
                    ticket_id=item.ticket_id,
                    score=score,
                    reason=reason,
                    signal_matches=tuple(signals),
                    title=item.title,
                    status=item.status,
                    updated_at=item.updated_at.isoformat() if item.updated_at else None,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: self._max_candidates]

    @classmethod
    def _score(cls, left: Ticket, right: Ticket) -> tuple[float, list[str]]:
        left_text = cls._text_blob(left)
        right_text = cls._text_blob(right)
        ratio = SequenceMatcher(None, left_text, right_text).ratio() if left_text and right_text else 0.0
        jaccard = cls._token_jaccard(left_text, right_text)
        score = max(ratio, jaccard)
        signals: list[str] = []
        if jaccard >= 0.35:
            signals.append("token_overlap")
        if ratio >= 0.55:
            signals.append("message_similarity")

        if left.intent == right.intent and left.intent:
            score += 0.16
            signals.append("same_intent")
        if left.session_id == right.session_id:
            score += 0.12
            signals.append("same_session")
        if left.channel == right.channel:
            score += 0.08
            signals.append("same_channel")

        time_gap_hours = cls._time_gap_hours(left.updated_at, right.updated_at)
        if time_gap_hours is not None and time_gap_hours <= 72:
            score += 0.08
            signals.append("recent_activity")
        elif time_gap_hours is not None and time_gap_hours <= 168:
            score += 0.05
            signals.append("same_week_activity")

        return min(1.0, score), signals

    @classmethod
    def _text_blob(cls, ticket: Ticket) -> str:
        text = f"{ticket.title} {ticket.latest_message}".lower()
        tokens = cls._TOKEN_RE.findall(text)
        return " ".join(tokens)

    @classmethod
    def _token_jaccard(cls, left: str, right: str) -> float:
        left_tokens = set(cls._TOKEN_RE.findall(left))
        right_tokens = set(cls._TOKEN_RE.findall(right))
        if not left_tokens or not right_tokens:
            return 0.0
        union = left_tokens | right_tokens
        if not union:
            return 0.0
        return len(left_tokens & right_tokens) / len(union)

    @staticmethod
    def _time_gap_hours(left: datetime | None, right: datetime | None) -> float | None:
        if left is None or right is None:
            return None
        normalized_left = left if left.tzinfo else left.replace(tzinfo=UTC)
        normalized_right = right if right.tzinfo else right.replace(tzinfo=UTC)
        return abs((normalized_left - normalized_right).total_seconds()) / 3600.0
