from __future__ import annotations

from typing import Literal, cast

from core.retrieval.reranker import Reranker
from core.retrieval.source_attribution import build_source_payloads
from core.retriever import Retriever
from storage.models import KBDocument

_RERANKER = Reranker()


def search_kb(
    *,
    retriever: Retriever,
    source_type: str,
    query: str,
    top_k: int = 3,
    retrieval_mode: str | None = None,
) -> list[dict[str, object]]:
    requested_source = source_type.lower().strip()
    effective_source = _normalize_source(requested_source)
    mode = _normalize_mode(requested_source=requested_source, requested_mode=retrieval_mode)
    if effective_source == "grounded":
        candidates = retriever.search_grounded_with_details(query, top_k=top_k, mode=mode)
    else:
        candidates = retriever.search_with_details(
            effective_source,
            query,
            top_k=max(3, top_k),
            mode=mode,
        )
    reranked = _RERANKER.rerank(query, candidates, top_k=top_k)
    attributions = build_source_payloads(query, reranked, top_k=top_k)
    by_source_id = {str(item["source_id"]): item for item in attributions}

    output: list[dict[str, object]] = []
    for idx, row in enumerate(reranked, start=1):
        raw_doc = row.get("doc")
        if not isinstance(raw_doc, KBDocument):
            continue
        doc = raw_doc
        source_id = doc.doc_id
        attribution = by_source_id.get(source_id, {})
        reason = str(
            attribution.get("reason")
            or row.get("rerank_reason")
            or _ranking_reason(
                requested_source=requested_source, doc_source=str(doc.source_type), mode=mode
            )
        )
        output.append(
            {
                "doc_id": doc.doc_id,
                "source_id": source_id,
                "source_type": doc.source_type,
                "title": doc.title,
                "content": doc.content,
                "tags": doc.tags,
                "score": _as_float(row.get("score"), default=doc.score),
                "rank": _as_int(row.get("rank"), default=idx),
                "ranking_reason": reason,
                "reason": reason,
                "snippet": str(attribution.get("snippet") or doc.content[:72]),
                "lexical_score": _as_float(row.get("lexical_score"), default=0.0),
                "vector_score": _as_float(row.get("vector_score"), default=0.0),
                "retrieval_mode": str(row.get("retrieval_mode", mode)),
                "updated_at": row.get("updated_at"),
                "metadata": row.get("metadata"),
            }
        )
    return output


def _normalize_source(source_type: str) -> str:
    if source_type in {"history", "history_case"}:
        return "history_case"
    if source_type in {"grounded", "hybrid"}:
        return "grounded"
    if source_type in {"faq", "sop"}:
        return source_type
    raise ValueError(f"Unsupported source_type: {source_type}")


def _normalize_mode(
    *, requested_source: str, requested_mode: str | None
) -> Literal["lexical", "vector", "hybrid"]:
    normalized_mode = (requested_mode or "").strip().lower()
    if normalized_mode in {"lexical", "vector", "hybrid"}:
        return cast(Literal["lexical", "vector", "hybrid"], normalized_mode)
    if requested_source in {"grounded", "hybrid"}:
        return "hybrid"
    return "lexical"


def _ranking_reason(*, requested_source: str, doc_source: str, mode: str) -> str:
    if requested_source in {"grounded", "hybrid"}:
        if doc_source == "history_case":
            return f"{mode}_grounded_rank:history_case_priority"
        if doc_source == "sop":
            return f"{mode}_grounded_rank:sop_secondary"
        if doc_source == "faq":
            return f"{mode}_grounded_rank:faq_fallback"
        return f"{mode}_grounded_rank:other_source"
    return f"{mode}_rank:score_desc"


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
