from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseRepository(ABC):
    @abstractmethod
    def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def get(self, entity_id: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        pass

    @abstractmethod
    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def count(self, filters: dict[str, Any] | None = None) -> int:
        pass
