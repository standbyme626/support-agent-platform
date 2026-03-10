from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from channel_adapters.base import BaseChannelAdapter, ChannelAdapterError
from storage.models import InboundEnvelope, OutboundEnvelope


class WeComAdapter(BaseChannelAdapter):
    channel = "wecom"

    def verify_inbound(self, payload: dict[str, Any]) -> None:
        signature = payload.get("signature")
        if not signature:
            return

        secret = str(payload.get("secret") or "")
        timestamp = str(payload.get("timestamp") or "")
        nonce = str(payload.get("nonce") or "")
        if not secret or not timestamp or not nonce:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_signature_fields",
                message="wecom signature verification requires secret/timestamp/nonce",
            )

        try:
            ts_int = int(timestamp)
        except ValueError as exc:
            raise ChannelAdapterError(
                channel=self.channel,
                code="invalid_timestamp",
                message="invalid wecom timestamp",
            ) from exc

        if abs(int(time.time()) - ts_int) > 300:
            raise ChannelAdapterError(
                channel=self.channel,
                code="replay_window_exceeded",
                message="wecom timestamp exceeds replay window",
            )

        expected = hmac.new(
            secret.encode(),
            f"{timestamp}:{nonce}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(str(signature), expected):
            raise ChannelAdapterError(
                channel=self.channel,
                code="invalid_signature",
                message="wecom signature mismatch",
            )

    def idempotency_key(self, payload: dict[str, Any]) -> str | None:
        msg_id = payload.get("MsgId")
        if msg_id:
            return f"{self.channel}:{msg_id}"
        session_id = payload.get("FromUserName") or payload.get("session_id")
        create_time = payload.get("CreateTime")
        if session_id and create_time:
            return f"{self.channel}:{session_id}:{create_time}"
        return None

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        msg_id = payload.get("MsgId")
        session_id = str(payload.get("FromUserName") or payload.get("session_id") or "")
        message_text = str(payload.get("Content") or payload.get("text") or "")
        if not session_id:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_session_id",
                message="wecom inbound payload missing FromUserName/session_id",
                context={"required_fields": ["FromUserName", "session_id"]},
            )
        if not message_text:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_message_text",
                message="wecom inbound payload missing Content/text",
                context={"required_fields": ["Content", "text"]},
            )
        inbox = str(payload.get("inbox") or f"{self.channel}.default")
        external_message_id = msg_id or payload.get("CreateTime")
        key_source = "MsgId" if msg_id else "FromUserName+CreateTime"
        metadata = {
            "msg_id": msg_id,
            "agent_id": payload.get("AgentID"),
            "create_time": payload.get("CreateTime"),
            "inbox": inbox,
            "conversation_id": session_id,
            "external_message_id": external_message_id,
            "contract_version": "wecom.v2",
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
            "touser": envelope.session_id,
            "msgtype": "text",
            "text": {"content": envelope.body},
            "metadata": envelope.metadata,
        }
