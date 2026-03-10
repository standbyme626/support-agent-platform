from __future__ import annotations

from core.retriever import Retriever


def search_kb(
    *,
    retriever: Retriever,
    source_type: str,
    query: str,
    top_k: int = 3,
) -> list[dict[str, object]]:
    if source_type == "faq":
        docs = retriever.search_faq(query, top_k=top_k)
    elif source_type == "sop":
        docs = retriever.search_sop(query, top_k=top_k)
    elif source_type in {"history", "history_case"}:
        docs = retriever.search_history(query, top_k=top_k)
    elif source_type in {"grounded", "hybrid"}:
        docs = retriever.search_grounded(query, top_k=top_k)
    else:
        raise ValueError(f"Unsupported source_type: {source_type}")

    normalized_source = source_type.lower()
    output: list[dict[str, object]] = []
    for idx, doc in enumerate(docs, start=1):
        output.append(
            {
                "doc_id": doc.doc_id,
                "source_type": doc.source_type,
                "title": doc.title,
                "content": doc.content,
                "tags": doc.tags,
                "score": doc.score,
                "rank": idx,
                "ranking_reason": _ranking_reason(
                    requested_source=normalized_source,
                    doc_source=doc.source_type,
                ),
            }
        )
    return output


def _ranking_reason(*, requested_source: str, doc_source: str) -> str:
    if requested_source in {"grounded", "hybrid"}:
        if doc_source == "history_case":
            return "grounded_rank:history_case_priority"
        if doc_source == "sop":
            return "grounded_rank:sop_secondary"
        if doc_source == "faq":
            return "grounded_rank:faq_fallback"
        return "grounded_rank:other_source"
    return "lexical_rank:score_desc"
