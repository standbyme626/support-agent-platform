from __future__ import annotations

from storage.models import Ticket, TicketEvent

from .model_adapter import ModelAdapter


class SummaryEngine:
    def __init__(self, model_adapter: ModelAdapter | None = None) -> None:
        self._model_adapter = model_adapter

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
            return fallback

        model_vars = {key: str(value) for key, value in variables.items()}
        try:
            return self._model_adapter.generate(task, model_vars)
        except Exception:
            return fallback
