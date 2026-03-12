from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from storage.models import KBDocument


@dataclass(frozen=True)
class SourceAttribution:
    source_type: str
    source_id: str
    title: str
    snippet: str
    score: float
    rank: int
    reason: str
    lexical_score: float
    vector_score: float
    retrieval_mode: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def build_source_attributions(
    query: str,
    candidates: Sequence[Mapping[str, object]],
    *,
    top_k: int | None = None,
) -> list[SourceAttribution]:
    terms = _tokenize(query)
    items = candidates if top_k is None else candidates[: max(1, top_k)]
    attributions: list[SourceAttribution] = []
    for index, row in enumerate(items, start=1):
        doc_raw = row.get("doc")
        if not isinstance(doc_raw, KBDocument):
            continue
        reason = str(row.get("rerank_reason") or row.get("ranking_reason") or "source:retrieved")
        attributions.append(
            SourceAttribution(
                source_type=doc_raw.source_type,
                source_id=doc_raw.doc_id,
                title=doc_raw.title,
                snippet=_snippet(doc_raw.content, terms=terms),
                score=_as_float(row.get("score"), default=doc_raw.score),
                rank=_as_int(row.get("rank"), default=index),
                reason=reason,
                lexical_score=_as_float(row.get("lexical_score"), default=0.0),
                vector_score=_as_float(row.get("vector_score"), default=0.0),
                retrieval_mode=str(row.get("retrieval_mode", "lexical")),
            )
        )
    return attributions


def build_source_payloads(
    query: str,
    candidates: Sequence[Mapping[str, object]],
    *,
    top_k: int | None = None,
) -> list[dict[str, object]]:
    return [item.as_dict() for item in build_source_attributions(query, candidates, top_k=top_k)]


def _tokenize(text: str) -> list[str]:
    normalized = text.lower().replace("，", " ").replace("。", " ").replace("/", " ")
    return [part for part in normalized.split() if part]


def _snippet(content: str, *, terms: list[str], size: int = 72) -> str:
    text = content.strip()
    if not text:
        return ""
    if not terms:
        return text[:size]
    lower = text.lower()
    for term in terms:
        index = lower.find(term)
        if index < 0:
            continue
        start = max(0, index - (size // 3))
        end = min(len(text), start + size)
        return text[start:end]
    return text[:size]


def _as_float(raw: object, *, default: float) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return default
    return default


def _as_int(raw: object, *, default: int) -> int:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return default
    return default
