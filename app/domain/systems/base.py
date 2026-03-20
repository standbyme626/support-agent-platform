from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SystemKey(str, Enum):
    TICKET = "ticket"
    PROCUREMENT = "procurement"
    FINANCE = "finance"
    APPROVAL = "approval"
    HR = "hr"
    ASSET = "asset"
    KB = "kb"
    CRM = "crm"
    PROJECT = "project"
    SUPPLY_CHAIN = "supply_chain"

    @classmethod
    def all(cls) -> list[str]:
        return [s.value for s in cls]


@dataclass(frozen=True)
class SystemAction:
    name: str
    allowed_from: frozenset[str]
    to_status: str
    required_fields: tuple[str, ...] = field(default_factory=tuple)


class BaseSystem(ABC):
    """十系统基类，定义统一接口"""

    @property
    @abstractmethod
    def system_key(self) -> str:
        """系统唯一标识"""
        pass

    @property
    @abstractmethod
    def entity_type(self) -> str:
        """主实体类型"""
        pass

    @property
    @abstractmethod
    def id_prefix(self) -> str:
        """ID前缀，如 T-、PR-、INV-"""
        pass

    @property
    @abstractmethod
    def lifecycle(self) -> tuple[str, ...]:
        """生命周期状态序列"""
        pass

    @property
    @abstractmethod
    def terminal_status(self) -> str:
        """终态"""
        pass

    @property
    def actions(self) -> dict[str, SystemAction]:
        """系统支持的动作定义"""
        return {}

    @abstractmethod
    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """创建实体"""
        pass

    @abstractmethod
    def get(self, entity_id: str) -> dict[str, Any] | None:
        """查询实体"""
        pass

    @abstractmethod
    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """列表查询"""
        pass

    @abstractmethod
    def execute_action(
        self,
        entity_id: str,
        action: str,
        operator_id: str,
        payload: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        """执行动作"""
        pass

    def validate_transition(self, current_status: str, action: str) -> bool:
        """校验状态迁移是否合法"""
        action_def = self.actions.get(action)
        if action_def is None:
            return False
        return current_status in action_def.allowed_from

    def next_status(self, action: str) -> str | None:
        """获取动作后的下一状态"""
        action_def = self.actions.get(action)
        if action_def is None:
            return None
        return action_def.to_status
