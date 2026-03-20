from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from storage.models import KBDocument

_DOC_SCHEMA_KEYS = {"doc_id", "source_type", "title", "content", "tags", "updated_at", "metadata"}
_SOURCE_ALIASES: dict[str, str] = {
    "history": "history_case",
    "history_case": "history_case",
    "faq": "faq",
    "sop": "sop",
}
_DEFAULT_UPDATED_AT = "1970-01-01T00:00:00+00:00"


@dataclass(frozen=True)
class NormalizedDocument:
    doc_id: str
    source_type: str
    title: str
    content: str
    tags: tuple[str, ...] = ()
    updated_at: str = _DEFAULT_UPDATED_AT
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_kb_document(self, *, score: float = 0.0) -> KBDocument:
        return KBDocument(
            doc_id=self.doc_id,
            source_type=self.source_type,
            title=self.title,
            content=self.content,
            tags=list(self.tags),
            score=score,
            updated_at=self.updated_at,
            metadata=dict(self.metadata),
        )


def load_normalized_documents(seed_root: Path) -> list[NormalizedDocument]:
    source_dirs: list[tuple[str, str, str]] = [
        ("faq", "faq_documents.json", "faq"),
        ("sop", "sop_documents.json", "sop"),
        ("historical_cases", "history_documents.json", "history_case"),
    ]
    docs: list[NormalizedDocument] = []
    for source_dir, primary_file, fallback_source in source_dirs:
        for path in _discover_seed_files(seed_root / source_dir, primary_file=primary_file):
            docs.extend(_load_file(path, fallback_source=fallback_source))
    return docs


def _discover_seed_files(source_dir: Path, *, primary_file: str) -> list[Path]:
    if not source_dir.exists():
        return []
    candidates = [path for path in source_dir.glob("*.json") if path.is_file()]
    if not candidates:
        return []
    return sorted(
        candidates,
        key=lambda path: (0 if path.name == primary_file else 1, path.name),
    )


def _load_file(path: Path, *, fallback_source: str) -> list[NormalizedDocument]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []

    docs: list[NormalizedDocument] = []
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            continue
        doc = _normalize_document(
            raw,
            fallback_source=fallback_source,
            source_path=path,
            default_doc_id=f"{fallback_source}-{index:04d}",
        )
        docs.append(doc)
    return docs


def _normalize_document(
    raw: dict[str, Any], *, fallback_source: str, source_path: Path, default_doc_id: str
) -> NormalizedDocument:
    legacy_source = str(raw.get("source_type", fallback_source)).strip().lower()
    source_type = _SOURCE_ALIASES.get(legacy_source, fallback_source)

    tags_raw = raw.get("tags")
    tags = _normalize_tags(tags_raw)
    metadata = _normalize_metadata(raw, source_path=source_path, legacy_source=legacy_source)
    updated_at_raw = raw.get("updated_at")
    updated_at = (
        str(updated_at_raw).strip() if isinstance(updated_at_raw, str) else _DEFAULT_UPDATED_AT
    )
    if not updated_at:
        updated_at = _DEFAULT_UPDATED_AT

    doc_id_value = str(raw.get("doc_id", default_doc_id)).strip()
    return NormalizedDocument(
        doc_id=doc_id_value or default_doc_id,
        source_type=source_type,
        title=str(raw.get("title", "")).strip(),
        content=str(raw.get("content", "")).strip(),
        tags=tags,
        updated_at=updated_at,
        metadata=metadata,
    )


def _normalize_tags(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return tuple(normalized)


def _normalize_metadata(
    raw: dict[str, Any], *, source_path: Path, legacy_source: str
) -> dict[str, Any]:
    metadata_raw = raw.get("metadata")
    metadata: dict[str, Any] = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
    metadata.setdefault("source_file", source_path.name)
    if legacy_source and legacy_source != _SOURCE_ALIASES.get(legacy_source, legacy_source):
        metadata["legacy_source_type"] = legacy_source
    extras = {key: value for key, value in raw.items() if key not in _DOC_SCHEMA_KEYS}
    if extras:
        metadata.setdefault("extras", extras)
    return metadata
