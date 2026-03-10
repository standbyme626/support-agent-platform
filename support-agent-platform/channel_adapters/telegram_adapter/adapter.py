from __future__ import annotations

from typing import Any

from channel_adapters.base import BaseChannelAdapter
from storage.models import InboundEnvelope, OutboundEnvelope


class TelegramAdapter(BaseChannelAdapter):
    channel = "telegram"

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        message = payload.get("message", {})
        chat = message.get("chat", {})
        session_id = str(chat.get("id") or payload.get("session_id") or "")
        message_text = str(message.get("text") or payload.get("text") or "")
        metadata = {
            "update_id": payload.get("update_id"),
            "username": chat.get("username"),
        }
        return InboundEnvelope(
            channel=self.channel,
            session_id=session_id,
            message_text=message_text,
            metadata=metadata,
        )

    def build_outbound(self, envelope: OutboundEnvelope) -> dict[str, object]:
        return {
            "chat_id": envelope.session_id,
            "text": envelope.body,
            "metadata": envelope.metadata,
        }
