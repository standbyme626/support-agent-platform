from __future__ import annotations

from app.domain.systems.adapters.base_adapter import ERPNextAdapter
from app.domain.systems.adapters.config import ERPNextConfig
from app.domain.systems.adapters.erpnext_asset import ERPNextAssetAdapter
from app.domain.systems.adapters.erpnext_client import ERPNextClient
from app.domain.systems.adapters.erpnext_crm import ERPNextCrmAdapter
from app.domain.systems.adapters.erpnext_finance import ERPNextFinanceAdapter
from app.domain.systems.adapters.erpnext_hr import ERPNextHrAdapter
from app.domain.systems.adapters.erpnext_procurement import (
    ERPNextProcurementAdapter,
)
from app.domain.systems.adapters.erpnext_supply_chain import (
    ERPNextSupplyChainAdapter,
)

__all__ = [
    "ERPNextAdapter",
    "ERPNextClient",
    "ERPNextConfig",
    "ERPNextProcurementAdapter",
    "ERPNextFinanceAdapter",
    "ERPNextHrAdapter",
    "ERPNextAssetAdapter",
    "ERPNextSupplyChainAdapter",
    "ERPNextCrmAdapter",
]
