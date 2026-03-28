from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.systems.base import BaseSystem

from app.domain.systems.base import SystemKey


class SystemRegistry:
    _instance: SystemRegistry | None = None

    def __new__(cls) -> "SystemRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._systems = {}
        return cls._instance

    def register(self, system: "BaseSystem") -> None:
        self._systems[system.system_key] = system

    def get(self, system_key: str) -> "BaseSystem | None":
        return self._systems.get(system_key)

    def list_systems(self) -> list[str]:
        return list(self._systems.keys())

    def has_system(self, system_key: str) -> bool:
        return system_key in self._systems

    def validate_system_key(self, system_key: str) -> bool:
        return system_key in SystemKey.all()

    def reset(self) -> None:
        self._systems.clear()

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None


registry = SystemRegistry()
