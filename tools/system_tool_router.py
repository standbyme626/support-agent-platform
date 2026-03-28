from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tools.create_asset import (
    create_asset,
    execute_asset_action,
    get_asset,
    list_asset,
)
from tools.create_crm import (
    create_crm,
    execute_crm_action,
    get_crm,
    list_crm,
)
from tools.create_finance import (
    create_finance,
    execute_finance_action,
    get_finance,
    list_finance,
)
from tools.create_hr import (
    create_hr,
    execute_hr_action,
    get_hr,
    list_hr,
)
from tools.create_procurement import (
    create_procurement,
    execute_procurement_action,
    get_procurement,
    list_procurement,
)
from tools.create_supply_chain import (
    create_supply_chain,
    execute_supply_chain_action,
    get_supply_chain,
    list_supply_chain,
)


@dataclass(frozen=True)
class SystemToolExecutionResult:
    tool_name: str
    output: Any


SYSTEM_KEYS = {
    "procurement",
    "hr",
    "finance",
    "supply_chain",
    "asset",
    "crm",
}


class SystemToolRouter:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {
            "procurement.create": create_procurement,
            "procurement.get": get_procurement,
            "procurement.list": list_procurement,
            "procurement.execute": execute_procurement_action,
            "hr.create": create_hr,
            "hr.get": get_hr,
            "hr.list": list_hr,
            "hr.execute": execute_hr_action,
            "finance.create": create_finance,
            "finance.get": get_finance,
            "finance.list": list_finance,
            "finance.execute": execute_finance_action,
            "supply_chain.create": create_supply_chain,
            "supply_chain.get": get_supply_chain,
            "supply_chain.list": list_supply_chain,
            "supply_chain.execute": execute_supply_chain_action,
            "asset.create": create_asset,
            "asset.get": get_asset,
            "asset.list": list_asset,
            "asset.execute": execute_asset_action,
            "crm.create": create_crm,
            "crm.get": get_crm,
            "crm.list": list_crm,
            "crm.execute": execute_crm_action,
        }

    @property
    def available_tools(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers.keys()))

    def execute(self, tool_name: str, args: dict[str, Any]) -> SystemToolExecutionResult:
        if tool_name not in self._handlers:
            raise ValueError(f"Unsupported tool '{tool_name}'")

        output = self._handlers[tool_name](args)
        return SystemToolExecutionResult(tool_name=tool_name, output=output)
