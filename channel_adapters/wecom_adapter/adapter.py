from __future__ import annotations

from typing import Any

from channel_adapters.base import BaseChannelAdapter
from storage.models import InboundEnvelope, OutboundEnvelope


class WeComAdapter(BaseChannelAdapter):
    channel = "wecom"

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        session_id = str(payload.get("FromUserName") or payload.get("session_id") or "")
        message_text = str(payload.get("Content") or payload.get("text") or "")
        inbox = str(payload.get("inbox") or f"{self.channel}.default")
        metadata = {
            "msg_id": payload.get("MsgId"),
            "agent_id": payload.get("AgentID"),
            "inbox": inbox,
            "conversation_id": session_id,
        }
        return InboundEnvelope(
            channel=self.channel,
            session_id=session_id,
            message_text=message_text,
            metadata=metadata,
        )

    def build_outbound(self, envelope: OutboundEnvelope) -> dict[str, object]:
        return {
            "touser": envelope.session_id,
            "msgtype": "text",
            "text": {"content": envelope.body},
            "metadata": envelope.metadata,
        }
