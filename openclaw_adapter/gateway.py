from __future__ import annotations

from dataclasses import asdict
from typing import Any

from channel_adapters.base import ChannelAdapterError
from storage.models import OutboundEnvelope

from .bindings import GatewayBindings, build_default_bindings
from .inbound_handler import InboundHandler
from .outbound_sender import OutboundSender


class OpenClawGateway:
    """Minimal OpenClaw integration: ingress/session/routing only."""

    def __init__(self, bindings: GatewayBindings | None = None) -> None:
        self._bindings = bindings or build_default_bindings()
        self._inbound_handler = InboundHandler(self._bindings)
        self._outbound_sender = OutboundSender(self._bindings)

    @property
    def bindings(self) -> GatewayBindings:
        return self._bindings

    def receive(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            inbound = self._inbound_handler.handle(channel, payload)
            trace_id = str(inbound.metadata.get("trace_id", ""))
            outbound = OutboundEnvelope(
                channel=inbound.channel,
                session_id=inbound.session_id,
                body=f"[gateway-ack] {inbound.message_text}",
                metadata=inbound.metadata,
            )
            rendered_outbound = self._outbound_sender.send(outbound)
            return {
                "status": "ok",
                "trace_id": trace_id,
                "inbound": asdict(inbound),
                "outbound": rendered_outbound,
            }
        except ChannelAdapterError as error:
            trace_id = str(payload.get("trace_id") or "")
            self._bindings.trace_logger.log(
                "ingress_failed",
                {
                    "channel": channel,
                    "error": error.to_dict(),
                },
                trace_id=trace_id or None,
                session_id=str(payload.get("session_id") or ""),
            )
            if error.code == "duplicate_webhook":
                return {
                    "status": "duplicate_ignored",
                    "trace_id": trace_id,
                    "error": error.to_dict(),
                }
            return {
                "status": "error",
                "trace_id": trace_id,
                "error": error.to_dict(),
            }

    def bind_ticket(
        self, session_id: str, ticket_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self._bindings.session_mapper.set_ticket_id(session_id, ticket_id, metadata=metadata)
        self._bindings.trace_logger.log(
            "gateway_bind_ticket",
            {"ticket_id": ticket_id, "metadata": metadata or {}},
            trace_id=str((metadata or {}).get("trace_id", "")) or None,
            ticket_id=ticket_id,
            session_id=session_id,
        )
