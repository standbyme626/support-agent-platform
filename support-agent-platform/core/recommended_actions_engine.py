from __future__ import annotations

from dataclasses import dataclass

from storage.models import KBDocument, Ticket

from .intent_router import IntentDecision


@dataclass(frozen=True)
class RecommendedAction:
    action: str
    reason: str
    source: str
    risk: str


class RecommendedActionsEngine:
    def recommend(
        self,
        *,
        ticket: Ticket,
        intent: IntentDecision,
        retrieved_docs: list[KBDocument],
        sla_breaches: list[str],
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        if intent.is_low_confidence:
            actions.append(
                RecommendedAction(
                    action="向用户追问关键信息",
                    reason="意图置信度较低，需要补充上下文",
                    source="intent_router",
                    risk="误分流风险",
                )
            )

        if ticket.priority == "P1" or "resolution_overdue" in sla_breaches:
            actions.append(
                RecommendedAction(
                    action="立即升级到值班负责人",
                    reason="高优先级或SLA违约",
                    source="sla_engine",
                    risk="响应延迟风险",
                )
            )

        if ticket.intent == "complaint":
            actions.append(
                RecommendedAction(
                    action="触发人工接管",
                    reason="投诉类工单需要人工兜底",
                    source="handoff_policy",
                    risk="客户满意度风险",
                )
            )

        if retrieved_docs:
            top_doc = retrieved_docs[0]
            actions.append(
                RecommendedAction(
                    action=f"参考文档: {top_doc.title}",
                    reason="检索到相似知识条目",
                    source=top_doc.source_type,
                    risk="知识过期风险",
                )
            )

        return actions[:4]
