from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.trace_logger import new_trace_id
from storage.models import InboundEnvelope

from .bindings import GatewayBindings


class InboundHandler:
    """Translate raw channel payload to normalized ingress envelope."""

    def __init__(self, bindings: GatewayBindings) -> None:
        self._bindings = bindings

    def handle(self, channel: str, payload: dict[str, Any]) -> InboundEnvelope:
        adapter = self._bindings.channel_router.resolve(channel)
        inbound = adapter.build_inbound(payload)
        trace_id = str(
            payload.get("trace_id") or inbound.metadata.get("trace_id") or new_trace_id()
        )

        binding = self._bindings.session_mapper.get_or_create(
            session_id=inbound.session_id,
            metadata={"channel": inbound.channel, "trace_id": trace_id, **inbound.metadata},
        )
        passthrough_metadata = {
            **inbound.metadata,
            "trace_id": trace_id,
            "thread_id": binding.thread_id,
            "ticket_id": binding.ticket_id,
        }
        enriched_inbound = replace(inbound, metadata=passthrough_metadata)

        self._bindings.trace_logger.log(
            "ingress_normalized",
            {
                "channel": inbound.channel,
                "session_id": inbound.session_id,
                "thread_id": binding.thread_id,
                "ticket_id": binding.ticket_id,
            },
            trace_id=trace_id,
            ticket_id=binding.ticket_id,
            session_id=inbound.session_id,
        )
        return enriched_inbound
