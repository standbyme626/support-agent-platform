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

    return [
        {
            "doc_id": doc.doc_id,
            "source_type": doc.source_type,
            "title": doc.title,
            "content": doc.content,
            "tags": doc.tags,
            "score": doc.score,
        }
        for doc in docs
    ]
