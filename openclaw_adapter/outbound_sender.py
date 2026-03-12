from __future__ import annotations

from channel_adapters.base import ChannelAdapterError
from storage.models import OutboundEnvelope

from .bindings import GatewayBindings
from .retry_manager import RetryManager


class OutboundSender:
    """Render normalized outbound envelope through the target channel adapter."""

    def __init__(self, bindings: GatewayBindings) -> None:
        self._bindings = bindings
        self._retry_manager = RetryManager()

    def send(self, outbound: OutboundEnvelope, *, retries: int = 2) -> dict[str, object]:
        adapter = self._bindings.channel_router.resolve(outbound.channel)
        trace_id = str(outbound.metadata.get("trace_id", ""))
        ticket_id = outbound.metadata.get("ticket_id")
        max_attempts = retries + 1

        last_error: ChannelAdapterError | None = None
        for attempt in range(max_attempts):
            attempt_no = attempt + 1
            try:
                payload = adapter.build_outbound(outbound)
                self._bindings.trace_logger.log(
                    "egress_rendered",
                    {
                        "channel": outbound.channel,
                        "session_id": outbound.session_id,
                        "payload": payload,
                        "attempt": attempt_no,
                        "max_attempts": max_attempts,
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
                    retryable=attempt_no < max_attempts,
                    context={"attempt": attempt_no},
                )

            if last_error is None:
                continue
            decision = self._retry_manager.decide(
                error=last_error,
                attempt=attempt_no,
                max_attempts=max_attempts,
            )
            self._bindings.trace_logger.log(
                "egress_failed",
                {
                    "channel": outbound.channel,
                    "session_id": outbound.session_id,
                    "attempt": attempt_no,
                    "max_attempts": max_attempts,
                    "error": (last_error.to_dict() if last_error else {}),
                    "retry": decision.to_payload(),
                },
                trace_id=trace_id or None,
                ticket_id=str(ticket_id) if ticket_id else None,
                session_id=outbound.session_id,
            )
            if decision.should_retry:
                self._bindings.trace_logger.log(
                    "egress_retry_scheduled",
                    {
                        "channel": outbound.channel,
                        "session_id": outbound.session_id,
                        "attempt": attempt_no,
                        "next_attempt": attempt_no + 1,
                        "max_attempts": max_attempts,
                        "retry": decision.to_payload(),
                    },
                    trace_id=trace_id or None,
                    ticket_id=str(ticket_id) if ticket_id else None,
                    session_id=outbound.session_id,
                )
                continue

            self._bindings.trace_logger.log(
                "egress_retry_exhausted",
                {
                    "channel": outbound.channel,
                    "session_id": outbound.session_id,
                    "attempt": attempt_no,
                    "max_attempts": max_attempts,
                    "retry": decision.to_payload(),
                },
                trace_id=trace_id or None,
                ticket_id=str(ticket_id) if ticket_id else None,
                session_id=outbound.session_id,
            )
            if last_error is not None:
                raise last_error

        raise RuntimeError("unreachable")
