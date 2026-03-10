from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from storage.models import KBDocument


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

    def __init__(self, seed_root: Path) -> None:
        self._seed_root = seed_root
        self._documents = self._load_documents()

    def search_faq(self, query: str, *, top_k: int = 3) -> list[KBDocument]:
        return self.search("faq", query, top_k=top_k)

    def search_sop(self, query: str, *, top_k: int = 3) -> list[KBDocument]:
        return self.search("sop", query, top_k=top_k)

    def search_history(self, query: str, *, top_k: int = 3) -> list[KBDocument]:
        return self.search("history_case", query, top_k=top_k)

    def search_grounded(self, query: str, *, top_k: int = 5) -> list[KBDocument]:
        fan_out = max(top_k, 6)
        history = self.search(
            "history_case",
            query,
            top_k=fan_out,
            source_boost=self._GROUND_SOURCE_BOOST["history_case"],
        )
        sop = self.search(
            "sop",
            query,
            top_k=fan_out,
            source_boost=self._GROUND_SOURCE_BOOST["sop"],
        )
        faq = self.search(
            "faq",
            query,
            top_k=fan_out,
            source_boost=self._GROUND_SOURCE_BOOST["faq"],
        )
        merged = [*history, *sop, *faq]
        query_terms = self._tokenize(query)
        ranked: list[KBDocument] = []
        for item in merged:
            ranking_score = self._grounded_score(item, query_terms=query_terms)
            ranked.append(
                KBDocument(
                    doc_id=item.doc_id,
                    source_type=item.source_type,
                    title=item.title,
                    content=item.content,
                    tags=list(item.tags),
                    score=ranking_score,
                )
            )

        ranked.sort(
            key=lambda doc: (
                doc.score,
                self._GROUND_SOURCE_PRIORITY.get(doc.source_type, 0),
            ),
            reverse=True,
        )
        return ranked[:top_k]

    def search(
        self, source_type: str, query: str, *, top_k: int = 3, source_boost: float = 0.0
    ) -> list[KBDocument]:
        docs = [doc for doc in self._documents if doc.source_type == source_type]
        terms = self._tokenize(query)

        scored: list[KBDocument] = []
        for doc in docs:
            score = self._score(doc, terms) + source_boost
            if score <= 0:
                continue
            scored.append(
                KBDocument(
                    doc_id=doc.doc_id,
                    source_type=doc.source_type,
                    title=doc.title,
                    content=doc.content,
                    tags=list(doc.tags),
                    score=score,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _load_documents(self) -> list[KBDocument]:
        files = [
            self._seed_root / "faq" / "faq_documents.json",
            self._seed_root / "sop" / "sop_documents.json",
            self._seed_root / "historical_cases" / "history_documents.json",
        ]

        docs: list[KBDocument] = []
        for path in files:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            for raw in payload:
                docs.append(
                    KBDocument(
                        doc_id=str(raw["doc_id"]),
                        source_type=str(raw["source_type"]),
                        title=str(raw["title"]),
                        content=str(raw["content"]),
                        tags=[str(tag) for tag in raw.get("tags", [])],
                    )
                )
        return docs

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        normalized = text.lower().replace("，", " ").replace("。", " ").replace("/", " ")
        return {part for part in normalized.split() if part}

    @staticmethod
    def _score(doc: KBDocument, terms: set[str]) -> float:
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
