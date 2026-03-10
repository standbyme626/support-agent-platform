from __future__ import annotations

from channel_adapters.base import ChannelAdapterError
from storage.models import OutboundEnvelope

from .bindings import GatewayBindings


class OutboundSender:
    """Render normalized outbound envelope through the target channel adapter."""

    def __init__(self, bindings: GatewayBindings) -> None:
        self._bindings = bindings

    def send(self, outbound: OutboundEnvelope, *, retries: int = 2) -> dict[str, object]:
        adapter = self._bindings.channel_router.resolve(outbound.channel)
        trace_id = str(outbound.metadata.get("trace_id", ""))
        ticket_id = outbound.metadata.get("ticket_id")

        last_error: ChannelAdapterError | None = None
        for attempt in range(retries + 1):
            try:
                payload = adapter.build_outbound(outbound)
                self._bindings.trace_logger.log(
                    "egress_rendered",
                    {
                        "channel": outbound.channel,
                        "session_id": outbound.session_id,
                        "payload": payload,
                        "attempt": attempt + 1,
                    },
                    trace_id=trace_id or None,
                    ticket_id=str(ticket_id) if ticket_id else None,
                    session_id=outbound.session_id,
                )
                return payload
            except ChannelAdapterError as error:
                last_error = error
            except Exception as error:  # pragma: no cover - defensive wrapper
                last_error = ChannelAdapterError(
                    channel=outbound.channel,
                    code="outbound_render_failed",
                    message=str(error),
                    retryable=attempt < retries,
                    context={"attempt": attempt + 1},
                )

            self._bindings.trace_logger.log(
                "egress_failed",
                {
                    "channel": outbound.channel,
                    "session_id": outbound.session_id,
                    "attempt": attempt + 1,
                    "error": (last_error.to_dict() if last_error else {}),
                },
                trace_id=trace_id or None,
                ticket_id=str(ticket_id) if ticket_id else None,
                session_id=outbound.session_id,
            )
            if last_error is not None and (not last_error.retryable or attempt >= retries):
                raise last_error

        raise RuntimeError("unreachable")
