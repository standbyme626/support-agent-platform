"""系统命令路由器 - 为 6 个业务系统提供命令行操作"""

from __future__ import annotations

import re
from typing import Any

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.erpnext_procurement import ERPNextProcurementAdapter
from app.domain.systems.adapters.erpnext_hr import ERPNextHrAdapter
from app.domain.systems.adapters.erpnext_finance import ERPNextFinanceAdapter
from app.domain.systems.adapters.erpnext_supply_chain import ERPNextSupplyChainAdapter
from app.domain.systems.adapters.erpnext_asset import ERPNextAssetAdapter
from app.domain.systems.adapters.erpnext_crm import ERPNextCrmAdapter


SYSTEM_ADAPTERS: dict[str, type[ERPNextAdapter]] = {
    "procurement": ERPNextProcurementAdapter,
    "hr": ERPNextHrAdapter,
    "finance": ERPNextFinanceAdapter,
    "supply_chain": ERPNextSupplyChainAdapter,
    "asset": ERPNextAssetAdapter,
    "crm": ERPNextCrmAdapter,
}


def parse_command(command_line: str) -> tuple[str, list[str]]:
    """解析命令，返回 (command, args)"""
    normalized = command_line.strip()
    if not normalized.startswith("/"):
        raise ValueError("命令必须以 / 开头")

    parts = normalized[1:].split()
    if not parts:
        raise ValueError("空命令")

    return parts[0].lower(), parts[1:]


def normalize_command(command: str) -> str:
    """标准化命令"""
    return command.strip().lower().replace("_", "-")


class SystemCommandRouter:
    """系统命令路由器"""

    # 命令映射: 命令名 -> (系统, 操作)
    COMMAND_MAP = {
        # procurement 命令
        "approve": ("procurement", "approve"),
        "reject": ("procurement", "reject"),
        "order": ("procurement", "order"),
        "receive": ("procurement", "receive"),
        "invoice": ("procurement", "invoice"),
        "close": ("procurement", "close"),
        # hr 命令
        "onboard": ("hr", "onboard"),
        "activate": ("hr", "activate"),
        "offboard": ("hr", "offboard"),
        "transfer": ("hr", "transfer"),
        # finance 命令
        "submit": ("finance", "submit"),
        "cancel": ("finance", "cancel"),
        # supply_chain 命令
        "receive-item": ("supply_chain", "receive_item"),
        "ship": ("supply_chain", "ship"),
        # asset 命令
        "capitalize": ("asset", "capitalize"),
        "maintain": ("asset", "maintain"),
        "dispose": ("asset", "dispose"),
        # crm 命令
        "assign-customer": ("crm", "assign"),
        "close-customer": ("crm", "close"),
    }

    # 中文自然语言映射
    CHINESE_NATURAL_MAP = {
        "创建采购": ("procurement", "create"),
        "创建订单": ("procurement", "create"),
        "审批": ("procurement", "approve"),
        "批准": ("procurement", "approve"),
        "驳回": ("procurement", "reject"),
        "拒绝": ("procurement", "reject"),
        "下单": ("procurement", "order"),
        "收货": ("procurement", "receive"),
        "创建员工": ("hr", "create"),
        "入职": ("hr", "onboard"),
        "激活": ("hr", "activate"),
        "离职": ("hr", "offboard"),
        "转岗": ("hr", "transfer"),
        "创建凭证": ("finance", "create"),
        "创建财务": ("finance", "create"),
        "财务凭证": ("finance", "create"),
        "提交": ("finance", "submit"),
        "取消": ("finance", "cancel"),
        "创建入库": ("supply_chain", "create"),
        "入库": ("supply_chain", "receive_item"),
        "出库": ("supply_chain", "ship"),
        "创建资产": ("asset", "create"),
        "资本化": ("asset", "capitalize"),
        "维保": ("asset", "maintain"),
        "处置": ("asset", "dispose"),
        "创建客户": ("crm", "create"),
        "创建商机": ("crm", "create"),
        "指派客户": ("crm", "assign"),
        "关闭客户": ("crm", "close"),
    }

    def __init__(self):
        self._adapters: dict[str, ERPNextAdapter] = {}

    def _get_adapter(self, system: str) -> ERPNextAdapter:
        if system not in self._adapters:
            if system not in SYSTEM_ADAPTERS:
                raise ValueError(f"未知系统: {system}")
            self._adapters[system] = SYSTEM_ADAPTERS[system]()
        return self._adapters[system]

    def handle_command(
        self,
        command_line: str,
        entity_id: str | None = None,
        operator_id: str = "system",
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """处理命令"""
        try:
            command, args = parse_command(command_line)
        except ValueError:
            return self._handle_natural(command_line, entity_id, operator_id, payload, trace_id)

        command = normalize_command(command)

        if command in self.COMMAND_MAP:
            system, action = self.COMMAND_MAP[command]
            return self._execute_action(system, action, entity_id, operator_id, payload, trace_id)

        return {
            "ok": False,
            "error": f"未知命令: /{command}",
            "available_commands": list(self.COMMAND_MAP.keys()),
        }

    def _handle_natural(
        self,
        text: str,
        entity_id: str | None,
        operator_id: str,
        payload: dict[str, Any] | None,
        trace_id: str | None,
    ) -> dict[str, Any]:
        """处理中文自然语言"""
        text = text.strip()

        for pattern, (system, action) in self.CHINESE_NATURAL_MAP.items():
            if pattern in text:
                # create 命令不需要 entity_id
                if action == "create":
                    adapter = self._get_adapter(system)
                    result = adapter.create(payload or {})
                    return result
                return self._execute_action(
                    system, action, entity_id, operator_id, payload, trace_id
                )

        return {
            "ok": False,
            "error": f"无法识别: {text}",
            "hint": "可使用命令如 /approve, /reject 或中文如 '审批', '批准' 等",
        }

    def _execute_action(
        self,
        system: str,
        action: str,
        entity_id: str | None,
        operator_id: str,
        payload: dict[str, Any] | None,
        trace_id: str | None,
    ) -> dict[str, Any]:
        """执行动作"""
        if entity_id is None:
            return {
                "ok": False,
                "error": f"执行 {action} 需要实体ID",
            }

        adapter = self._get_adapter(system)

        if action == "create":
            result = adapter.create(payload or {})
        else:
            result = adapter.execute_action(
                entity_id=entity_id,
                action=action,
                operator_id=operator_id,
                payload=payload or {},
                trace_id=trace_id or "system-cmd",
            )

        return result


_command_router = SystemCommandRouter()


def handle_system_command(
    command_line: str,
    entity_id: str | None = None,
    operator_id: str = "system",
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """处理系统命令的入口函数"""
    return _command_router.handle_command(command_line, entity_id, operator_id, payload, trace_id)
