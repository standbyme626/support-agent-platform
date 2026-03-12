from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Protocol

from llm.manager import LLMGenerationError
from storage.models import KBDocument, Ticket, TicketEvent

from .handoff_manager import HandoffDecision
from .intent_router import IntentDecision
from .recommended_actions_engine import RecommendedAction

ReplyGenerationType = Literal["faq", "progress", "handoff", "generic"]


class ReplyModelAdapter(Protocol):
    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = ...,
    ) -> tuple[str, dict[str, Any]]: ...


@dataclass(frozen=True)
class ReplyGenerationResult:
    reply_text: str
    generation_type: ReplyGenerationType
    metadata: dict[str, Any]


class ReplyGenerator:
    """Generate employee-facing reply with LLM-first and safe fallback."""

    _PROMPT_BY_TYPE: ClassVar[dict[ReplyGenerationType, str]] = {
        "faq": "faq_reply",
        "progress": "progress_reply",
        "handoff": "handoff_reply",
        "generic": "intake_user_reply",
    }

    def __init__(
        self,
        model_adapter: ReplyModelAdapter | None = None,
        *,
        system_prompt: str = "你是内部服务台客服助手。回答要自然、具体、可执行，避免空泛套话。",
    ) -> None:
        self._model_adapter = model_adapter
        self._system_prompt = system_prompt

    def generate(
        self,
        *,
        message_text: str,
        intent: IntentDecision,
        ticket: Ticket,
        retrieved_docs: list[KBDocument],
        summary: str,
        recommendations: list[RecommendedAction],
        handoff: HandoffDecision,
        events: list[TicketEvent],
        fallback_reply: str,
        tone: str = "professional_warm",
    ) -> ReplyGenerationResult:
        generation_type = self._resolve_generation_type(intent, handoff)
        prompt_key = self._PROMPT_BY_TYPE[generation_type]
        grounding_sources = [f"{doc.source_type}:{doc.doc_id}" for doc in retrieved_docs[:5]]

        if self._model_adapter is None:
            return self._fallback_result(
                fallback_reply=fallback_reply,
                generation_type=generation_type,
                prompt_key=prompt_key,
                grounding_sources=grounding_sources,
                tone=tone,
                reason="llm_disabled",
            )

        variables = self._build_variables(
            message_text=message_text,
            intent=intent,
            ticket=ticket,
            summary=summary,
            retrieved_docs=retrieved_docs,
            recommendations=recommendations,
            handoff=handoff,
            events=events,
            tone=tone,
        )
        try:
            raw_text, trace = self._model_adapter.generate_with_trace(
                prompt_key,
                variables,
                system_prompt=self._system_prompt,
            )
        except LLMGenerationError as exc:
            reason = self._infer_degrade_reason(str(exc.trace_metadata.get("error") or str(exc)))
            return self._fallback_result(
                fallback_reply=fallback_reply,
                generation_type=generation_type,
                prompt_key=prompt_key,
                grounding_sources=grounding_sources,
                tone=tone,
                reason=reason,
                trace_metadata=exc.trace_metadata,
            )
        except Exception as exc:  # pragma: no cover - defensive path
            reason = self._infer_degrade_reason(str(exc))
            return self._fallback_result(
                fallback_reply=fallback_reply,
                generation_type=generation_type,
                prompt_key=prompt_key,
                grounding_sources=grounding_sources,
                tone=tone,
                reason=reason,
                trace_metadata={"error": str(exc)},
            )

        normalized_trace = self._normalize_trace_metadata(prompt_key=prompt_key, metadata=trace)
        try:
            parsed = self._parse_structured_reply(raw_text)
            reply_text = parsed["reply_text"]
        except ValueError as exc:
            normalized_trace["error"] = str(exc)
            normalized_trace["success"] = False
            normalized_trace["fallback_used"] = True
            normalized_trace["degraded"] = True
            normalized_trace["degrade_reason"] = "schema_parse_error"
            return self._fallback_result(
                fallback_reply=fallback_reply,
                generation_type=generation_type,
                prompt_key=prompt_key,
                grounding_sources=grounding_sources,
                tone=tone,
                reason="schema_parse_error",
                trace_metadata=normalized_trace,
            )

        normalized_trace.update(
            {
                "generation_type": generation_type,
                "tone": tone,
                "grounding_sources": grounding_sources,
            }
        )
        return ReplyGenerationResult(
            reply_text=reply_text,
            generation_type=generation_type,
            metadata=normalized_trace,
        )

    @staticmethod
    def _resolve_generation_type(
        intent: IntentDecision, handoff: HandoffDecision
    ) -> ReplyGenerationType:
        if handoff.should_handoff:
            return "handoff"
        if intent.intent == "faq":
            return "faq"
        if intent.intent == "progress_query":
            return "progress"
        return "generic"

    @staticmethod
    def _build_variables(
        *,
        message_text: str,
        intent: IntentDecision,
        ticket: Ticket,
        summary: str,
        retrieved_docs: list[KBDocument],
        recommendations: list[RecommendedAction],
        handoff: HandoffDecision,
        events: list[TicketEvent],
        tone: str,
    ) -> dict[str, str]:
        grounding = [
            {
                "doc_id": doc.doc_id,
                "source_type": doc.source_type,
                "title": doc.title,
                "score": doc.score,
            }
            for doc in retrieved_docs[:3]
        ]
        recommendation_payload = [
            {
                "action": item.action,
                "reason": item.reason,
                "source": item.source,
                "risk": item.risk,
                "confidence": item.confidence,
                "evidence": [
                    {"doc_id": evidence.doc_id, "source_type": evidence.source_type}
                    for evidence in item.evidence
                ],
            }
            for item in recommendations[:3]
        ]
        latest_events = [
            {
                "event_type": event.event_type,
                "actor": event.actor_id,
            }
            for event in events[-5:]
        ]
        return {
            "user_message": message_text,
            "intent": intent.intent,
            "intent_confidence": f"{intent.confidence:.2f}",
            "ticket_id": ticket.ticket_id,
            "ticket_status": ticket.status,
            "ticket_priority": ticket.priority,
            "ticket_queue": ticket.queue,
            "ticket_assignee": ticket.assignee or "unassigned",
            "handoff_decision": "true" if handoff.should_handoff else "false",
            "handoff_reason": handoff.reason,
            "summary": summary,
            "grounding_sources": json.dumps(grounding, ensure_ascii=False),
            "recommendations": json.dumps(recommendation_payload, ensure_ascii=False),
            "latest_events": json.dumps(latest_events, ensure_ascii=False),
            "tone": tone,
        }

    @staticmethod
    def _parse_structured_reply(raw_text: str) -> dict[str, str]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = ReplyGenerator._strip_code_fence(cleaned)
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError("reply schema must be a JSON object")
        reply_text = payload.get("reply_text")
        if not isinstance(reply_text, str) or not reply_text.strip():
            raise ValueError("reply schema missing non-empty reply_text")
        return {"reply_text": reply_text.strip()}

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return ""
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _normalize_trace_metadata(*, prompt_key: str, metadata: dict[str, Any]) -> dict[str, Any]:
        trace = dict(metadata)
        trace.setdefault("provider", "openai_compatible")
        trace.setdefault("model", None)
        trace.setdefault("prompt_key", prompt_key)
        trace.setdefault("prompt_version", None)
        trace.setdefault("latency_ms", None)
        trace.setdefault("request_id", None)
        trace.setdefault("token_usage", None)
        trace.setdefault("retry_count", 0)
        trace.setdefault("success", True)
        trace.setdefault("error", None)
        trace.setdefault("fallback_used", False)
        trace.setdefault(
            "degraded",
            bool(trace.get("fallback_used")) or not bool(trace.get("success")),
        )
        trace.setdefault("degrade_reason", None)
        return trace

    def _fallback_result(
        self,
        *,
        fallback_reply: str,
        generation_type: ReplyGenerationType,
        prompt_key: str,
        grounding_sources: list[str],
        tone: str,
        reason: str,
        trace_metadata: dict[str, Any] | None = None,
    ) -> ReplyGenerationResult:
        raw_trace = dict(trace_metadata or {})
        metadata = self._normalize_trace_metadata(prompt_key=prompt_key, metadata=raw_trace)
        metadata.update(
            {
                "provider": str(metadata.get("provider") or "fallback"),
                "success": False,
                "fallback_used": True,
                "degraded": True,
                "degrade_reason": reason,
                "generation_type": generation_type,
                "tone": tone,
                "grounding_sources": grounding_sources,
            }
        )
        if not metadata.get("error"):
            metadata["error"] = reason
        return ReplyGenerationResult(
            reply_text=fallback_reply,
            generation_type=generation_type,
            metadata=metadata,
        )

    @staticmethod
    def _infer_degrade_reason(error: str) -> str:
        lowered = error.lower()
        if "timeout" in lowered:
            return "llm_timeout"
        if "schema" in lowered or "json" in lowered:
            return "schema_parse_error"
        return "llm_provider_error"
