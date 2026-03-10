from __future__ import annotations

from typing import Any

from channel_adapters.base import BaseChannelAdapter
from storage.models import InboundEnvelope, OutboundEnvelope


class FeishuAdapter(BaseChannelAdapter):
    channel = "feishu"

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        event = payload.get("event", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        session_id = str(
            sender_id.get("open_id") or sender_id.get("union_id") or payload.get("session_id") or ""
        )
        message_text = str(event.get("message", {}).get("text") or payload.get("text") or "")
        metadata = {
            "message_id": event.get("message", {}).get("message_id"),
            "tenant_key": payload.get("tenant_key"),
        }
        return InboundEnvelope(
            channel=self.channel,
            session_id=session_id,
            message_text=message_text,
            metadata=metadata,
        )

    def build_outbound(self, envelope: OutboundEnvelope) -> dict[str, object]:
        return {
            "receive_id": envelope.session_id,
            "msg_type": "text",
            "content": {"text": envelope.body},
            "metadata": envelope.metadata,
        }
