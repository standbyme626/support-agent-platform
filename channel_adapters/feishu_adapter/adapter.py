from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from channel_adapters.base import BaseChannelAdapter, ChannelAdapterError
from storage.models import InboundEnvelope, OutboundEnvelope


class FeishuAdapter(BaseChannelAdapter):
    channel = "feishu"

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
                message="feishu signature verification requires secret/timestamp/nonce",
            )

        try:
            ts_int = int(timestamp)
        except ValueError as exc:
            raise ChannelAdapterError(
                channel=self.channel,
                code="invalid_timestamp",
                message="invalid feishu timestamp",
            ) from exc

        if abs(int(time.time()) - ts_int) > 300:
            raise ChannelAdapterError(
                channel=self.channel,
                code="replay_window_exceeded",
                message="feishu timestamp exceeds replay window",
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
                message="feishu signature mismatch",
            )

    def idempotency_key(self, payload: dict[str, Any]) -> str | None:
        message_id = payload.get("event", {}).get("message", {}).get("message_id")
        if message_id:
            return f"{self.channel}:{message_id}"
        event_id = payload.get("event_id")
        if event_id:
            return f"{self.channel}:{event_id}"
        return None

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        event = payload.get("event", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        message_id = event.get("message", {}).get("message_id")
        session_id = str(
            sender_id.get("open_id") or sender_id.get("union_id") or payload.get("session_id") or ""
        )
        message_text = str(event.get("message", {}).get("text") or payload.get("text") or "")
        if not session_id:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_session_id",
                message="feishu inbound payload missing sender_id/session_id",
                context={"required_fields": ["event.sender.sender_id.open_id", "session_id"]},
            )
        if not message_text:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_message_text",
                message="feishu inbound payload missing message.text/text",
                context={"required_fields": ["event.message.text", "text"]},
            )
        inbox = str(
            payload.get("inbox")
            or event.get("chat_id")
            or f"{self.channel}.default"
        )
        event_id = payload.get("event_id")
        external_message_id = message_id or event_id
        key_source = "message.message_id" if message_id else "event_id"
        metadata = {
            "message_id": message_id,
            "event_id": event_id,
            "tenant_key": payload.get("tenant_key"),
            "inbox": inbox,
            "conversation_id": session_id,
            "external_message_id": external_message_id,
            "contract_version": "feishu.v2",
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
            "receive_id": envelope.session_id,
            "msg_type": "text",
            "content": {"text": envelope.body},
            "metadata": envelope.metadata,
        }
