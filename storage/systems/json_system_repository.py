from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from storage.systems.base_repository import BaseRepository


class JSONSystemRepository(BaseRepository):
    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._file_path.exists():
            with open(self._file_path, encoding="utf-8") as f:
                self._cache = json.load(f)
        else:
            self._cache = {}

    def _save(self) -> None:
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            entity_id = entity.get("id") or entity.get("entity_id")
            if not entity_id:
                raise ValueError("Entity must have 'id' or 'entity_id'")
            self._cache[entity_id] = entity
            self._save()
            return entity

    def get(self, entity_id: str) -> dict[str, Any] | None:
        return self._cache.get(entity_id)

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            if entity_id not in self._cache:
                return None
            self._cache[entity_id].update(data)
            self._save()
            return self._cache[entity_id]

    def delete(self, entity_id: str) -> bool:
        with self._lock:
            if entity_id in self._cache:
                del self._cache[entity_id]
                self._save()
                return True
            return False

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        results = list(self._cache.values())

        if filters:
            results = [e for e in results if self._matches(e, filters)]

        offset = (page - 1) * page_size
        return results[offset : offset + page_size]

    def count(self, filters: dict[str, Any] | None = None) -> int:
        if not filters:
            return len(self._cache)
        return len([e for e in self._cache.values() if self._matches(e, filters)])

    @staticmethod
    def _matches(entity: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            if key not in entity:
                return False
            if isinstance(value, list):
                if entity[key] not in value:
                    return False
            elif entity[key] != value:
                return False
        return True
