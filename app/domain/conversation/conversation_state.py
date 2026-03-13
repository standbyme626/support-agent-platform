from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ConversationMode = Literal["faq", "support", "idle"]


@dataclass
class ConversationState:
    """Session-scoped state model for conversation context."""

    session_id: str
    active_ticket_id: str | None = None
    recent_ticket_ids: list[str] = field(default_factory=list)
    conversation_mode: ConversationMode = "idle"
    awaiting_customer_confirmation: bool = False
    last_user_intent: str | None = None

    def set_active_ticket(self, ticket_id: str) -> None:
        self.active_ticket_id = ticket_id
        if ticket_id not in self.recent_ticket_ids:
            self.recent_ticket_ids.insert(0, ticket_id)

    def clear_active_ticket(self) -> None:
        self.active_ticket_id = None
        self.awaiting_customer_confirmation = False

    def mark_waiting_customer(self, flag: bool) -> None:
        self.awaiting_customer_confirmation = flag
