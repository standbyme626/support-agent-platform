from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Literal, TypedDict

from core.retrieval.hybrid_retriever import HybridRetriever
from core.retrieval.normalized_docs import NormalizedDocument, load_normalized_documents
from core.retrieval.vector_retriever import VectorRetriever
from storage.models import KBDocument

RetrievalMode = Literal["lexical", "vector", "hybrid"]


class RetrievalDetail(TypedDict):
    doc: KBDocument
    score: float
    lexical_score: float
    vector_score: float
    retrieval_mode: str
    updated_at: str
    metadata: dict[str, Any]


class Retriever:
    """Local lexical retriever for FAQ/SOP/history-case documents."""

    _GROUND_SOURCE_BOOST: ClassVar[dict[str, float]] = {
        "history_case": 0.45,
        "sop": 0.18,
        "faq": 0.08,
    }
    _GROUND_SOURCE_PRIORITY: ClassVar[dict[str, int]] = {
        "history_case": 3,
        "sop": 2,
        "faq": 1,
    }
    _SOURCE_ALIASES: ClassVar[dict[str, str]] = {
        "history": "history_case",
        "history_case": "history_case",
        "faq": "faq",
        "sop": "sop",
    }

    def __init__(self, seed_root: Path) -> None:
        self._seed_root = seed_root
        self._normalized_documents = self._load_documents()
        self._vector_retriever = VectorRetriever(self._normalized_documents)
        self._hybrid_retriever = HybridRetriever(vector_retriever=self._vector_retriever)
        self._documents_by_source: dict[str, list[NormalizedDocument]] = {
            "faq": [],
            "sop": [],
            "history_case": [],
        }
        for doc in self._normalized_documents:
            source = self._normalize_source(doc.source_type)
            if source not in self._documents_by_source:
                self._documents_by_source[source] = []
            self._documents_by_source[source].append(doc)

    def search_faq(
        self, query: str, *, top_k: int = 3, mode: RetrievalMode = "lexical"
    ) -> list[KBDocument]:
        return self.search("faq", query, top_k=top_k, mode=mode)

    def search_sop(
        self, query: str, *, top_k: int = 3, mode: RetrievalMode = "lexical"
    ) -> list[KBDocument]:
        return self.search("sop", query, top_k=top_k, mode=mode)

    def search_history(
        self, query: str, *, top_k: int = 3, mode: RetrievalMode = "lexical"
    ) -> list[KBDocument]:
        return self.search("history_case", query, top_k=top_k, mode=mode)

    def search_grounded(
        self, query: str, *, top_k: int = 5, mode: RetrievalMode = "hybrid"
    ) -> list[KBDocument]:
        detailed = self.search_grounded_with_details(query, top_k=top_k, mode=mode)
        return [item["doc"] for item in detailed]

    def search_grounded_with_details(
        self, query: str, *, top_k: int = 5, mode: RetrievalMode = "hybrid"
    ) -> list[RetrievalDetail]:
        fan_out = max(top_k, 6)
        history = self.search_with_details(
            "history_case",
            query,
            top_k=fan_out,
            mode=mode,
            source_boost=self._GROUND_SOURCE_BOOST["history_case"],
        )
        sop = self.search_with_details(
            "sop",
            query,
            top_k=fan_out,
            mode=mode,
            source_boost=self._GROUND_SOURCE_BOOST["sop"],
        )
        faq = self.search_with_details(
            "faq",
            query,
            top_k=fan_out,
            mode=mode,
            source_boost=self._GROUND_SOURCE_BOOST["faq"],
        )
        merged = [*history, *sop, *faq]
        query_terms = self._tokenize(query)
        ranked: list[RetrievalDetail] = []
        for item in merged:
            raw_doc = item["doc"]
            ranking_score = self._grounded_score(raw_doc, query_terms=query_terms)
            grounded_doc = KBDocument(
                doc_id=raw_doc.doc_id,
                source_type=raw_doc.source_type,
                title=raw_doc.title,
                content=raw_doc.content,
                tags=list(raw_doc.tags),
                score=ranking_score,
            )
            ranked.append(
                {
                    **item,
                    "doc": grounded_doc,
                    "score": ranking_score,
                    "retrieval_mode": mode,
                }
            )

        ranked.sort(
            key=lambda item: (
                item["score"],
                self._GROUND_SOURCE_PRIORITY.get(item["doc"].source_type, 0),
            ),
            reverse=True,
        )
        return ranked[:top_k]

    def search(
        self,
        source_type: str,
        query: str,
        *,
        top_k: int = 3,
        source_boost: float = 0.0,
        mode: RetrievalMode = "lexical",
    ) -> list[KBDocument]:
        detailed: list[RetrievalDetail] = self.search_with_details(
            source_type,
            query,
            top_k=top_k,
            source_boost=source_boost,
            mode=mode,
        )
        return [
            KBDocument(
                doc_id=item["doc"].doc_id,
                source_type=item["doc"].source_type,
                title=item["doc"].title,
                content=item["doc"].content,
                tags=list(item["doc"].tags),
                score=item["score"],
            )
            for item in detailed
        ]

    def search_with_details(
        self,
        source_type: str,
        query: str,
        *,
        top_k: int = 3,
        source_boost: float = 0.0,
        mode: RetrievalMode = "lexical",
    ) -> list[RetrievalDetail]:
        normalized_source = self._normalize_source(source_type)
        docs = list(self._documents_by_source.get(normalized_source, []))
        terms = self._tokenize(query)
        lexical_scores = {doc.doc_id: self._score(doc, terms) for doc in docs}

        ranked: list[RetrievalDetail] = []
        if mode == "hybrid":
            combined = self._hybrid_retriever.combine(
                query=query,
                documents=docs,
                lexical_scores=lexical_scores,
                source_boost={normalized_source: source_boost},
                top_k=max(top_k, len(docs)),
            )
            for item in combined:
                ranked.append(
                    {
                        "doc": item.document.to_kb_document(score=item.score),
                        "score": item.score,
                        "lexical_score": item.lexical_score,
                        "vector_score": item.vector_score,
                        "retrieval_mode": mode,
                        "updated_at": item.document.updated_at,
                        "metadata": dict(item.document.metadata),
                    }
                )
        elif mode == "vector":
            vector_scores = self._vector_retriever.score_documents(query, documents=docs)
            for doc in docs:
                vector_score = vector_scores.get(doc.doc_id, 0.0)
                score = vector_score + source_boost
                if score <= 0:
                    continue
                ranked.append(
                    {
                        "doc": doc.to_kb_document(score=score),
                        "score": score,
                        "lexical_score": lexical_scores.get(doc.doc_id, 0.0),
                        "vector_score": vector_score,
                        "retrieval_mode": mode,
                        "updated_at": doc.updated_at,
                        "metadata": dict(doc.metadata),
                    }
                )
        else:
            for doc in docs:
                lexical_score = lexical_scores.get(doc.doc_id, 0.0)
                score = lexical_score + source_boost
                if score <= 0:
                    continue
                ranked.append(
                    {
                        "doc": doc.to_kb_document(score=score),
                        "score": score,
                        "lexical_score": lexical_score,
                        "vector_score": 0.0,
                        "retrieval_mode": "lexical",
                        "updated_at": doc.updated_at,
                        "metadata": dict(doc.metadata),
                    }
                )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:top_k]

    def _load_documents(self) -> list[NormalizedDocument]:
        return load_normalized_documents(self._seed_root)

    def source_stats(self) -> dict[str, int]:
        return {source: len(docs) for source, docs in self._documents_by_source.items()}

    @classmethod
    def _normalize_source(cls, source_type: str) -> str:
        return cls._SOURCE_ALIASES.get(source_type.lower(), source_type.lower())

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        normalized = text.lower().replace("，", " ").replace("。", " ").replace("/", " ")
        return {part for part in normalized.split() if part}

    @staticmethod
    def _score(doc: NormalizedDocument, terms: set[str]) -> float:
        if not terms:
            return 0.0

        haystack = f"{doc.title} {doc.content} {' '.join(doc.tags)}".lower()
        score = 0.0
        for term in terms:
            if term in haystack:
                score += 1.0
        return score / len(terms)

    def _grounded_score(self, doc: KBDocument, *, query_terms: set[str]) -> float:
        base = doc.score
        source_priority = self._GROUND_SOURCE_PRIORITY.get(doc.source_type, 0)
        priority_bonus = source_priority * 0.05
        if not query_terms:
            return base + priority_bonus

        title_text = doc.title.lower()
        title_hit_count = sum(1 for term in query_terms if term in title_text)
        title_bonus = (title_hit_count / len(query_terms)) * 0.2
        return base + priority_bonus + title_bonus
