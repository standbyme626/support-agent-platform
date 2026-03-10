from __future__ import annotations

from storage.models import OutboundEnvelope

from .bindings import GatewayBindings


class OutboundSender:
    """Render normalized outbound envelope through the target channel adapter."""

    def __init__(self, bindings: GatewayBindings) -> None:
        self._bindings = bindings

    def send(self, outbound: OutboundEnvelope) -> dict[str, object]:
        adapter = self._bindings.channel_router.resolve(outbound.channel)
        payload = adapter.build_outbound(outbound)
        trace_id = str(outbound.metadata.get("trace_id", ""))
        ticket_id = outbound.metadata.get("ticket_id")
        self._bindings.trace_logger.log(
            "egress_rendered",
            {
                "channel": outbound.channel,
                "session_id": outbound.session_id,
                "payload": payload,
            },
            trace_id=trace_id or None,
            ticket_id=str(ticket_id) if ticket_id else None,
            session_id=outbound.session_id,
        )
        return payload
