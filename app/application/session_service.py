from __future__ import annotations

from typing import Protocol

from app.domain.conversation.conversation_state import ConversationMode, ConversationState


class SessionContextStoreProtocol(Protocol):
    def get(self, session_id: str) -> ConversationState | None: ...

    def save(self, state: ConversationState) -> None: ...


class SessionService:
    """Conversation context service without ticket lifecycle mutations."""

    def __init__(self, session_store: SessionContextStoreProtocol) -> None:
        self._session_store = session_store

    def get_or_create(self, session_id: str) -> ConversationState:
        state = self._session_store.get(session_id)
        if state is not None:
            return state
        created = ConversationState(session_id=session_id)
        self._session_store.save(created)
        return created

    def set_active_ticket(self, session_id: str, ticket_id: str) -> ConversationState:
        state = self.get_or_create(session_id)
        state.set_active_ticket(ticket_id)
        self._session_store.save(state)
        return state

    def clear_active_ticket(self, session_id: str) -> ConversationState:
        state = self.get_or_create(session_id)
        state.clear_active_ticket()
        self._session_store.save(state)
        return state

    def mark_waiting_customer(self, session_id: str, ticket_id: str, flag: bool) -> ConversationState:
        state = self.get_or_create(session_id)
        if state.active_ticket_id != ticket_id:
            state.set_active_ticket(ticket_id)
        state.mark_waiting_customer(flag)
        self._session_store.save(state)
        return state

    def set_mode(self, session_id: str, mode: ConversationMode) -> ConversationState:
        state = self.get_or_create(session_id)
        state.conversation_mode = mode
        self._session_store.save(state)
        return state

    def set_last_intent(self, session_id: str, intent: str) -> ConversationState:
        state = self.get_or_create(session_id)
        state.last_user_intent = intent
        self._session_store.save(state)
        return state

    def end_session(self, session_id: str) -> ConversationState:
        state = self.get_or_create(session_id)
        state.clear_active_ticket()
        state.conversation_mode = "idle"
        self._session_store.save(state)
        return state
