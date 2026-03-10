from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from storage.models import KBDocument, Ticket

from .intent_router import IntentDecision


@dataclass(frozen=True)
class ActionEvidence:
    doc_id: str
    source_type: str


@dataclass(frozen=True)
class RecommendedAction:
    action: str
    reason: str
    source: str
    risk: str
    confidence: float
    evidence: tuple[ActionEvidence, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "source": self.source,
            "risk": self.risk,
            "confidence": self.confidence,
            "evidence": [
                {"doc_id": item.doc_id, "source_type": item.source_type}
                for item in self.evidence
            ],
        }


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
        primary_doc = self._pick_primary_doc(retrieved_docs)

        if intent.is_low_confidence:
            actions.append(
                RecommendedAction(
                    action="向用户追问关键信息",
                    reason="意图置信度较低，需要补充上下文",
                    source="intent_router",
                    risk="误分流风险",
                    confidence=_bounded_confidence(max(0.3, 1.0 - intent.confidence)),
                    evidence=(
                        ActionEvidence(
                            doc_id=f"intent:{intent.intent}",
                            source_type="intent_router",
                        ),
                    ),
                )
            )

        if ticket.priority == "P1" or any(
            item in {"first_response_overdue", "resolution_overdue"} for item in sla_breaches
        ):
            evidence: list[ActionEvidence] = [
                ActionEvidence(doc_id=f"sla:{item}", source_type="sla_policy")
                for item in sla_breaches
            ]
            if ticket.priority == "P1":
                evidence.append(
                    ActionEvidence(
                        doc_id=f"priority:{ticket.priority}",
                        source_type="ticket_field",
                    )
                )
            actions.append(
                RecommendedAction(
                    action="立即升级到值班负责人",
                    reason="高优先级或SLA违约",
                    source="sla_engine",
                    risk="响应延迟风险",
                    confidence=0.92 if ticket.priority == "P1" else 0.84,
                    evidence=tuple(evidence),
                )
            )

        if ticket.intent == "complaint":
            complaint_evidence: list[ActionEvidence] = [
                ActionEvidence(
                    doc_id=f"intent:{ticket.intent}",
                    source_type="ticket_field",
                )
            ]
            if primary_doc is not None:
                complaint_evidence.append(
                    ActionEvidence(doc_id=primary_doc.doc_id, source_type=primary_doc.source_type)
                )
            actions.append(
                RecommendedAction(
                    action="触发人工接管",
                    reason="投诉类工单需要人工兜底",
                    source="handoff_policy",
                    risk="客户满意度风险",
                    confidence=0.88,
                    evidence=tuple(complaint_evidence),
                )
            )

        if primary_doc:
            actions.append(
                RecommendedAction(
                    action=f"参考案例/知识: {primary_doc.title}",
                    reason="检索命中可复用历史处理经验",
                    source=f"{primary_doc.source_type}:{primary_doc.doc_id}",
                    risk="知识过期风险",
                    confidence=_bounded_confidence(primary_doc.score),
                    evidence=(
                        ActionEvidence(
                            doc_id=primary_doc.doc_id,
                            source_type=primary_doc.source_type,
                        ),
                    ),
                )
            )

        filtered = [item for item in actions if item.evidence]
        return filtered[:4]

    @staticmethod
    def _pick_primary_doc(docs: list[KBDocument]) -> KBDocument | None:
        if not docs:
            return None
        history_docs = [item for item in docs if item.source_type == "history_case"]
        if history_docs:
            history_docs.sort(key=lambda item: item.score, reverse=True)
            return history_docs[0]
        ranked_docs = sorted(docs, key=lambda item: item.score, reverse=True)
        return ranked_docs[0]


def _bounded_confidence(raw: float) -> float:
    return max(0.0, min(1.0, raw))
