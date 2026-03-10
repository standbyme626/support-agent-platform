from __future__ import annotations

from dataclasses import replace
from typing import Any

from channel_adapters.base import ChannelAdapterError
from core.trace_logger import new_trace_id
from storage.models import InboundEnvelope

from .bindings import GatewayBindings


class InboundHandler:
    """Translate raw channel payload to normalized ingress envelope."""

    def __init__(self, bindings: GatewayBindings) -> None:
        self._bindings = bindings

    def handle(self, channel: str, payload: dict[str, Any]) -> InboundEnvelope:
        adapter = self._bindings.channel_router.resolve(channel)
        adapter.verify_inbound(payload)
        inbound = adapter.build_inbound(payload)
        trace_id = str(
            payload.get("trace_id") or inbound.metadata.get("trace_id") or new_trace_id()
        )
        inbox = str(inbound.metadata.get("inbox") or f"{inbound.channel}.default")
        idempotency_key = (
            adapter.idempotency_key(payload)
            or str(inbound.metadata.get("external_message_id") or "")
            or None
        )

        binding = self._bindings.session_mapper.get_or_create(
            session_id=inbound.session_id,
            metadata={
                "channel": inbound.channel,
                "trace_id": trace_id,
                "inbox": inbox,
                **inbound.metadata,
            },
        )
        if idempotency_key:
            processed_message_ids = [
                str(item) for item in binding.metadata.get("processed_message_ids", [])
            ]
            if idempotency_key in processed_message_ids:
                raise ChannelAdapterError(
                    channel=inbound.channel,
                    code="duplicate_webhook",
                    message=f"duplicate inbound webhook: {idempotency_key}",
                    retryable=False,
                    context={"idempotency_key": idempotency_key},
                )
            processed_message_ids.append(idempotency_key)
            processed_message_ids = processed_message_ids[-30:]
            binding = self._bindings.session_mapper.get_or_create(
                session_id=inbound.session_id,
                metadata={
                    "processed_message_ids": processed_message_ids,
                    "last_message_id": idempotency_key,
                },
            )

        passthrough_metadata = {
            **inbound.metadata,
            "trace_id": trace_id,
            "inbox": inbox,
            "thread_id": binding.thread_id,
            "ticket_id": binding.ticket_id,
            "idempotency_key": idempotency_key,
        }
        enriched_inbound = replace(inbound, metadata=passthrough_metadata)

        self._bindings.trace_logger.log(
            "ingress_normalized",
            {
                "channel": inbound.channel,
                "session_id": inbound.session_id,
                "thread_id": binding.thread_id,
                "ticket_id": binding.ticket_id,
                "inbox": inbox,
                "idempotency_key": idempotency_key,
            },
            trace_id=trace_id,
            ticket_id=binding.ticket_id,
            session_id=inbound.session_id,
        )
        return enriched_inbound
