from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.systems.base import SystemKey


@dataclass
class IntentMapping:
    keywords: tuple[str, ...]
    system_key: str
    confidence: float = 1.0


INTENT_MAPPINGS: list[IntentMapping] = [
    IntentMapping(
        keywords=("采购", "请购", "购买", "PO", "procurement", "purchase"),
        system_key=SystemKey.PROCUREMENT,
    ),
    IntentMapping(
        keywords=("发票", "付款", "财务", "退款", "扣费", "对账", "finance", "invoice"),
        system_key=SystemKey.FINANCE,
    ),
    IntentMapping(
        keywords=("审批", "OA", "审核", "申请", "approval", "approve"),
        system_key=SystemKey.APPROVAL,
    ),
    IntentMapping(keywords=("入职", "HR", "工资", "转正", "招聘", "员工"), system_key=SystemKey.HR),
    IntentMapping(
        keywords=("资产", "设备", "领用", "报废", "工位", "asset"), system_key=SystemKey.ASSET
    ),
    IntentMapping(
        keywords=("知识库", "FAQ", "查询", "指引", "咨询", "kb", "knowledge"),
        system_key=SystemKey.KB,
    ),
    IntentMapping(keywords=("CRM", "客户", "case", "投诉", "合同"), system_key=SystemKey.CRM),
    IntentMapping(keywords=("项目", "立项", "迭代", "project"), system_key=SystemKey.PROJECT),
    IntentMapping(
        keywords=("供应链", "库存", "订单", "收货", "supply_chain"),
        system_key=SystemKey.SUPPLY_CHAIN,
    ),
    IntentMapping(keywords=("工单", "故障", "维修", "ticket", "IT"), system_key=SystemKey.TICKET),
]


class SystemIntentRouter:
    def route(self, text: str) -> str:
        if not text:
            return SystemKey.TICKET

        text_lower = text.lower()

        for mapping in INTENT_MAPPINGS:
            if any(kw.lower() in text_lower for kw in mapping.keywords):
                return mapping.system_key

        return SystemKey.TICKET

    def route_with_confidence(self, text: str) -> tuple[str, float]:
        if not text:
            return SystemKey.TICKET, 0.5

        text_lower = text.lower()

        best_match: IntentMapping | None = None
        best_score = 0

        for mapping in INTENT_MAPPINGS:
            score = sum(1 for kw in mapping.keywords if kw.lower() in text_lower)
            if score > best_score:
                best_score = score
                best_match = mapping

        if best_match and best_score > 0:
            return best_match.system_key, min(1.0, best_score * 0.5)

        return SystemKey.TICKET, 0.5

    def extract_fields(self, text: str, system_key: str) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        return fields
