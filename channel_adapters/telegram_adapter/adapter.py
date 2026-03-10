from __future__ import annotations

from typing import Any

from channel_adapters.base import BaseChannelAdapter, ChannelAdapterError
from storage.models import InboundEnvelope, OutboundEnvelope


class TelegramAdapter(BaseChannelAdapter):
    channel = "telegram"

    def idempotency_key(self, payload: dict[str, Any]) -> str | None:
        update_id = payload.get("update_id")
        if update_id is not None:
            return f"{self.channel}:{update_id}"
        message = payload.get("message", {})
        chat = message.get("chat", {})
        message_id = message.get("message_id")
        chat_id = chat.get("id")
        if message_id is not None and chat_id is not None:
            return f"{self.channel}:{chat_id}:{message_id}"
        return None

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        message = payload.get("message", {})
        chat = message.get("chat", {})
        update_id = payload.get("update_id")
        session_id = str(chat.get("id") or payload.get("session_id") or "")
        message_text = str(message.get("text") or payload.get("text") or "")
        if not session_id:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_session_id",
                message="telegram inbound payload missing chat.id/session_id",
                context={"required_fields": ["message.chat.id", "session_id"]},
            )
        if not message_text:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_message_text",
                message="telegram inbound payload missing message.text/text",
                context={"required_fields": ["message.text", "text"]},
            )
        inbox = str(payload.get("inbox") or f"{self.channel}.default")
        external_message_id = (
            update_id if update_id is not None else message.get("message_id")
        )
        key_source = "update_id" if update_id is not None else "message.message_id"
        metadata = {
            "update_id": update_id,
            "message_id": message.get("message_id"),
            "username": chat.get("username"),
            "inbox": inbox,
            "conversation_id": session_id,
            "external_message_id": external_message_id,
            "contract_version": "telegram.v2",
            "idempotency_key_source": key_source,
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
