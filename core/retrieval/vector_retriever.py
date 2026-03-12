from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import ClassVar

from .normalized_docs import NormalizedDocument


@dataclass(frozen=True)
class VectorSearchResult:
    document: NormalizedDocument
    score: float


class VectorRetriever:
    """Lightweight local vector retriever using hashed char/word features."""

    _CHINESE_RE: ClassVar[re.Pattern[str]] = re.compile(r"[\u4e00-\u9fff]+")

    def __init__(self, documents: Sequence[NormalizedDocument], *, dimensions: int = 384) -> None:
        self._documents = list(documents)
        self._dimensions = max(64, dimensions)
        self._doc_vectors: dict[str, dict[int, float]] = {}
        self._doc_norms: dict[str, float] = {}
        self._doc_index: dict[str, NormalizedDocument] = {}
        for doc in self._documents:
            vector = self._encode_document(doc)
            self._doc_vectors[doc.doc_id] = vector
            self._doc_norms[doc.doc_id] = _vector_norm(vector)
            self._doc_index[doc.doc_id] = doc

    def score_documents(
        self,
        query: str,
        *,
        documents: Sequence[NormalizedDocument] | None = None,
    ) -> dict[str, float]:
        query_vector = self._encode_text(query)
        if not query_vector:
            return {}
        query_norm = _vector_norm(query_vector)
        if query_norm <= 0:
            return {}

        if documents is None:
            candidates = self._documents
        else:
            candidates = list(documents)

        scores: dict[str, float] = {}
        for doc in candidates:
            doc_vector = self._doc_vectors.get(doc.doc_id)
            doc_norm = self._doc_norms.get(doc.doc_id, 0.0)
            if not doc_vector or doc_norm <= 0:
                continue
            dot = _dot_product(query_vector, doc_vector)
            if dot <= 0:
                continue
            scores[doc.doc_id] = dot / (query_norm * doc_norm)
        return scores

    def search(
        self,
        query: str,
        *,
        documents: Sequence[NormalizedDocument] | None = None,
        top_k: int = 3,
    ) -> list[VectorSearchResult]:
        scores = self.score_documents(query, documents=documents)
        if not scores:
            return []
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: max(1, top_k)]
        results: list[VectorSearchResult] = []
        for doc_id, score in ranked:
            doc = self._doc_index.get(doc_id)
            if doc is None:
                continue
            results.append(VectorSearchResult(document=doc, score=score))
        return results

    def _encode_document(self, doc: NormalizedDocument) -> dict[int, float]:
        combined = f"{doc.title} {doc.content} {' '.join(doc.tags)}"
        return self._encode_text(combined)

    def _encode_text(self, text: str) -> dict[int, float]:
        raw = (text or "").lower().strip()
        if not raw:
            return {}

        features: dict[int, float] = {}
        for token in _iter_features(raw):
            idx = _hash_to_bucket(token, dimensions=self._dimensions)
            features[idx] = features.get(idx, 0.0) + 1.0
        return features


def _iter_features(text: str) -> Iterable[str]:
    for token in text.replace("，", " ").replace("。", " ").replace("/", " ").split():
        cleaned = token.strip()
        if cleaned:
            yield f"w:{cleaned}"
    condensed = re.sub(r"\s+", "", text)
    if len(condensed) <= 1:
        if condensed:
            yield f"c:{condensed}"
        return
    for size in (2, 3):
        if len(condensed) < size:
            continue
        for index in range(0, len(condensed) - size + 1):
            yield f"n{size}:{condensed[index : index + size]}"


def _hash_to_bucket(token: str, *, dimensions: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big") % dimensions


def _dot_product(left: dict[int, float], right: dict[int, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    total = 0.0
    for idx, value in left.items():
        total += value * right.get(idx, 0.0)
    return total


def _vector_norm(vector: dict[int, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values()))
