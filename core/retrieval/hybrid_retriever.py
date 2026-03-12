from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .normalized_docs import NormalizedDocument
from .vector_retriever import VectorRetriever


@dataclass(frozen=True)
class HybridSearchResult:
    document: NormalizedDocument
    score: float
    lexical_score: float
    vector_score: float


class HybridRetriever:
    def __init__(
        self,
        *,
        vector_retriever: VectorRetriever,
        lexical_weight: float = 0.55,
        vector_weight: float = 0.45,
    ) -> None:
        self._vector_retriever = vector_retriever
        self._lexical_weight = lexical_weight
        self._vector_weight = vector_weight

    def combine(
        self,
        *,
        query: str,
        documents: Sequence[NormalizedDocument],
        lexical_scores: dict[str, float],
        source_boost: dict[str, float] | None = None,
        top_k: int = 3,
    ) -> list[HybridSearchResult]:
        vector_scores = self._vector_retriever.score_documents(query, documents=documents)
        boost_map = source_boost or {}
        ranked: list[HybridSearchResult] = []
        for doc in documents:
            lexical_score = lexical_scores.get(doc.doc_id, 0.0)
            vector_score = vector_scores.get(doc.doc_id, 0.0)
            boost = boost_map.get(doc.source_type, 0.0)
            score = (
                (lexical_score * self._lexical_weight)
                + (vector_score * self._vector_weight)
                + boost
            )
            if score <= 0:
                continue
            ranked.append(
                HybridSearchResult(
                    document=doc,
                    score=score,
                    lexical_score=lexical_score,
                    vector_score=vector_score,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: max(1, top_k)]
