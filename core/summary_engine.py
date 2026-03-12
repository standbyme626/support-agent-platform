from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Protocol, cast

from llm.manager import LLMGenerationError
from storage.models import Ticket, TicketEvent


class SummaryModelAdapter(Protocol):
    def generate(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
    ) -> str: ...


class TraceableSummaryModelAdapter(SummaryModelAdapter, Protocol):
    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = ...,
    ) -> tuple[str, dict[str, Any]]: ...


class SummaryEngine:
    def __init__(self, model_adapter: SummaryModelAdapter | None = None) -> None:
        self._model_adapter = model_adapter
        self._last_generation_metadata: dict[str, Any] = {}

    def intake_summary(self, ticket: Ticket) -> str:
        fallback = (
            f"工单{ticket.ticket_id} 来自{ticket.channel}，用户会话{ticket.session_id}，"
            f"意图={ticket.intent}，优先级={ticket.priority}。"
        )
        return self._render("intake_summary", fallback, ticket=ticket)

    def case_summary(self, ticket: Ticket, events: list[TicketEvent]) -> str:
        timeline = ", ".join(event.event_type for event in events[-5:]) or "无事件"
        fallback = (
            f"工单{ticket.ticket_id} 当前状态={ticket.status}，处理轨迹={timeline}，"
            f"最新消息={ticket.latest_message}。"
        )
        return self._render("case_summary", fallback, ticket=ticket, timeline=timeline)

    def wrap_up_summary(self, ticket: Ticket, events: list[TicketEvent], resolution: str) -> str:
        fallback = (
            f"工单{ticket.ticket_id} 已完成收尾，最终状态={ticket.status}，"
            f"处理事件数={len(events)}，结论={resolution}。"
        )
        return self._render("wrap_up_summary", fallback, ticket=ticket, resolution=resolution)

    def _render(self, task: str, fallback: str, **variables: object) -> str:
        if self._model_adapter is None:
            self._last_generation_metadata = self._fallback_metadata(
                task=task,
                reason="llm_disabled",
            )
            return fallback

        model_vars = {key: str(value) for key, value in variables.items()}
        try:
            if hasattr(self._model_adapter, "generate_with_trace"):
                traceable_adapter = cast(TraceableSummaryModelAdapter, self._model_adapter)
                text, metadata = traceable_adapter.generate_with_trace(task, model_vars)
                self._last_generation_metadata = self._normalize_metadata(task, metadata)
                return text
            text = self._model_adapter.generate(task, model_vars)
            self._last_generation_metadata = self._normalize_metadata(
                task,
                {
                    "provider": "openai_compatible",
                    "model": None,
                    "prompt_key": task,
                    "prompt_version": None,
                    "latency_ms": None,
                    "request_id": None,
                    "token_usage": None,
                    "retry_count": 0,
                    "success": True,
                    "error": None,
                    "fallback_used": False,
                },
            )
            return text
        except LLMGenerationError as exc:
            self._last_generation_metadata = self._normalize_metadata(task, exc.trace_metadata)
            return fallback
        except Exception as exc:
            self._last_generation_metadata = self._fallback_metadata(
                task=task,
                reason="llm_runtime_error",
                error=str(exc),
            )
            return fallback

    def last_generation_metadata(self) -> dict[str, Any]:
        return deepcopy(self._last_generation_metadata)

    @staticmethod
    def _normalize_metadata(task: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(metadata)
        payload.setdefault("provider", "openai_compatible")
        payload.setdefault("model", None)
        payload.setdefault("prompt_key", task)
        payload.setdefault("prompt_version", None)
        payload.setdefault("latency_ms", None)
        payload.setdefault("request_id", None)
        payload.setdefault("token_usage", None)
        payload.setdefault("retry_count", 0)
        payload.setdefault("success", False)
        payload.setdefault("error", None)
        payload.setdefault("fallback_used", False)
        payload.setdefault(
            "degraded",
            bool(payload.get("fallback_used")) or not bool(payload["success"]),
        )
        return payload

    @staticmethod
    def _fallback_metadata(task: str, reason: str, error: str | None = None) -> dict[str, Any]:
        return {
            "provider": "fallback",
            "model": None,
            "prompt_key": task,
            "prompt_version": None,
            "latency_ms": None,
            "request_id": None,
            "token_usage": None,
            "retry_count": 0,
            "success": False,
            "error": error or reason,
            "fallback_used": True,
            "degraded": True,
            "degrade_reason": reason,
        }


def compact_summary_text(text: str, *, max_chars: int = 280) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3]}..."


def build_handoff_summary(
    ticket: Ticket, events: list[TicketEvent], *, summary: str | None = None
) -> str:
    if summary:
        return compact_summary_text(summary)
    timeline = ",".join(event.event_type for event in events[-5:]) or "none"
    fallback = (
        f"ticket={ticket.ticket_id} status={ticket.status} "
        f"intent={ticket.intent} timeline={timeline}"
    )
    return compact_summary_text(fallback)
