from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from storage.models import KBDocument


class Reranker:
    def rerank(
        self,
        query: str,
        candidates: Sequence[Mapping[str, object]],
        *,
        top_k: int | None = None,
    ) -> list[dict[str, object]]:
        terms = _tokenize(query)
        rescored: list[dict[str, object]] = []
        for item in candidates:
            doc = item.get("doc")
            if not isinstance(doc, KBDocument):
                continue
            base_score = _as_float(item.get("score"), default=doc.score)
            rerank_score = self._score(
                doc,
                terms=terms,
                base_score=base_score,
                updated_at=item.get("updated_at"),
            )
            reason = self._reason(doc, terms=terms)
            rescored.append(
                {
                    **item,
                    "score": rerank_score,
                    "rerank_score": rerank_score,
                    "rerank_reason": reason,
                }
            )
        rescored.sort(
            key=lambda row: _as_float(
                row.get("rerank_score"), default=_as_float(row.get("score"), 0.0)
            ),
            reverse=True,
        )
        if top_k is not None:
            rescored = rescored[: max(1, top_k)]
        for index, item in enumerate(rescored, start=1):
            item["rank"] = index
        return rescored

    @staticmethod
    def _score(
        doc: KBDocument,
        *,
        terms: set[str],
        base_score: float,
        updated_at: object,
    ) -> float:
        if not terms:
            return base_score
        title = doc.title.lower()
        content = doc.content.lower()
        title_hits = sum(1 for term in terms if term in title)
        content_hits = sum(1 for term in terms if term in content)
        term_coverage = (title_hits + content_hits) / max(1, len(terms) * 2)
        title_bonus = (title_hits / max(1, len(terms))) * 0.15
        freshness_bonus = _freshness_bonus(updated_at)
        return base_score + (term_coverage * 0.2) + title_bonus + freshness_bonus

    @staticmethod
    def _reason(doc: KBDocument, *, terms: set[str]) -> str:
        if not terms:
            return "rerank:base_score"
        title = doc.title.lower()
        title_hits = sum(1 for term in terms if term in title)
        if title_hits > 0:
            return "rerank:title_match"
        return "rerank:content_match"


def _tokenize(text: str) -> set[str]:
    normalized = text.lower().replace("，", " ").replace("。", " ").replace("/", " ")
    return {part for part in normalized.split() if part}


def _freshness_bonus(updated_at: object) -> float:
    if not isinstance(updated_at, str) or not updated_at:
        return 0.0
    try:
        parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    days = max(0.0, (datetime.now(UTC) - parsed).total_seconds() / 86400.0)
    if days <= 30:
        return 0.06
    if days <= 180:
        return 0.03
    return 0.0


def _as_float(raw: object, default: float) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return default
    return default
