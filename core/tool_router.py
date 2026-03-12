from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tools.assign_ticket import assign_ticket
from tools.close_case import close_case
from tools.create_ticket import create_ticket
from tools.escalate_case import escalate_case
from tools.search_kb import search_kb
from tools.update_ticket import update_ticket

from .retriever import Retriever
from .ticket_api import TicketAPI
from .trace_logger import JsonTraceLogger


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    output: Any


class ToolRouter:
    """Boundary-only tool router with explicit input validation."""

    def __init__(
        self,
        ticket_api: TicketAPI,
        retriever: Retriever,
        trace_logger: JsonTraceLogger | None = None,
    ) -> None:
        self._ticket_api = ticket_api
        self._retriever = retriever
        self._trace_logger = trace_logger
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "search_kb": self._run_search_kb,
            "create_ticket": self._run_create_ticket,
            "update_ticket": self._run_update_ticket,
            "assign_ticket": self._run_assign_ticket,
            "close_case": self._run_close_case,
            "escalate_case": self._run_escalate_case,
        }

    @property
    def available_tools(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers.keys()))

    def execute(self, tool_name: str, args: dict[str, Any]) -> ToolExecutionResult:
        if tool_name not in self._handlers:
            raise ValueError(f"Unsupported tool '{tool_name}'")

        trace_id = self._extract_optional(args, "trace_id")
        ticket_id = self._extract_optional(args, "ticket_id")
        session_id = self._extract_optional(args, "session_id")
        self._log_tool_event(
            "tool_call_start",
            tool_name,
            {"args": {key: value for key, value in args.items() if key != "metadata"}},
            trace_id=trace_id,
            ticket_id=ticket_id,
            session_id=session_id,
        )
        try:
            output = self._handlers[tool_name](args)
        except Exception as exc:
            self._log_tool_event(
                "tool_call_error",
                tool_name,
                {"error": str(exc)},
                trace_id=trace_id,
                ticket_id=ticket_id,
                session_id=session_id,
            )
            raise
        self._log_tool_event(
            "tool_call_end",
            tool_name,
            {"output_preview": str(output)[:240]},
            trace_id=trace_id,
            ticket_id=ticket_id or self._extract_ticket_from_output(output),
            session_id=session_id,
        )
        return ToolExecutionResult(tool_name=tool_name, output=output)

    def _run_search_kb(self, args: dict[str, Any]) -> Any:
        source = str(args.get("source_type", "faq"))
        query = self._require_str(args, "query")
        top_k = int(args.get("top_k", 3))
        retrieval_mode = str(args.get("retrieval_mode", "")).strip() or None
        return search_kb(
            retriever=self._retriever,
            source_type=source,
            query=query,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
        )

    def _run_create_ticket(self, args: dict[str, Any]) -> Any:
        required = [
            "channel",
            "session_id",
            "thread_id",
            "title",
            "latest_message",
            "intent",
        ]
        for field in required:
            self._require_str(args, field)
        return create_ticket(ticket_api=self._ticket_api, payload=args)

    def _run_update_ticket(self, args: dict[str, Any]) -> Any:
        ticket_id = self._require_str(args, "ticket_id")
        actor_id = self._require_str(args, "actor_id")
        updates = dict(args.get("updates") or {})
        if not updates:
            raise ValueError("updates cannot be empty")
        return update_ticket(
            self._ticket_api, ticket_id=ticket_id, updates=updates, actor_id=actor_id
        )

    def _run_assign_ticket(self, args: dict[str, Any]) -> Any:
        return assign_ticket(
            self._ticket_api,
            ticket_id=self._require_str(args, "ticket_id"),
            assignee=self._require_str(args, "assignee"),
            actor_id=self._require_str(args, "actor_id"),
        )

    def _run_close_case(self, args: dict[str, Any]) -> Any:
        return close_case(
            self._ticket_api,
            ticket_id=self._require_str(args, "ticket_id"),
            actor_id=self._require_str(args, "actor_id"),
            resolution_note=self._require_str(args, "resolution_note"),
        )

    def _run_escalate_case(self, args: dict[str, Any]) -> Any:
        return escalate_case(
            self._ticket_api,
            ticket_id=self._require_str(args, "ticket_id"),
            actor_id=self._require_str(args, "actor_id"),
            reason=self._require_str(args, "reason"),
            new_priority=str(args.get("new_priority", "P1")),
        )

    @staticmethod
    def _require_str(args: dict[str, Any], field: str) -> str:
        value = args.get(field)
        if value is None:
            raise ValueError(f"Missing required field: {field}")
        text = str(value).strip()
        if not text:
            raise ValueError(f"Field '{field}' cannot be empty")
        return text

    @staticmethod
    def _extract_optional(args: dict[str, Any], field: str) -> str | None:
        value = args.get(field)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _extract_ticket_from_output(output: Any) -> str | None:
        if isinstance(output, dict) and "ticket_id" in output:
            return str(output["ticket_id"])
        return None

    def _log_tool_event(
        self,
        event_type: str,
        tool_name: str,
        payload: dict[str, Any],
        *,
        trace_id: str | None,
        ticket_id: str | None,
        session_id: str | None,
    ) -> None:
        if self._trace_logger is None:
            return
        self._trace_logger.log(
            event_type,
            {"tool_name": tool_name, **payload},
            trace_id=trace_id,
            ticket_id=ticket_id,
            session_id=session_id,
        )
