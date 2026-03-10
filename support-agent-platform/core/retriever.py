from __future__ import annotations

import json
from pathlib import Path

from storage.models import KBDocument


class Retriever:
    """Local lexical retriever for FAQ/SOP/history-case documents."""

    def __init__(self, seed_root: Path) -> None:
        self._seed_root = seed_root
        self._documents = self._load_documents()

    def search_faq(self, query: str, *, top_k: int = 3) -> list[KBDocument]:
        return self.search("faq", query, top_k=top_k)

    def search_sop(self, query: str, *, top_k: int = 3) -> list[KBDocument]:
        return self.search("sop", query, top_k=top_k)

    def search_history(self, query: str, *, top_k: int = 3) -> list[KBDocument]:
        return self.search("history_case", query, top_k=top_k)

    def search(self, source_type: str, query: str, *, top_k: int = 3) -> list[KBDocument]:
        docs = [doc for doc in self._documents if doc.source_type == source_type]
        terms = self._tokenize(query)

        scored: list[KBDocument] = []
        for doc in docs:
            score = self._score(doc, terms)
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
