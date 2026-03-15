from __future__ import annotations

from dataclasses import asdict
from typing import Any

from channel_adapters.base import ChannelAdapterError
from storage.models import OutboundEnvelope

from .bindings import GatewayBindings, build_default_bindings
from .inbound_handler import InboundHandler
from .outbound_sender import OutboundSender


class OpenClawGateway:
    """Minimal OpenClaw integration: ingress/session/routing only.

    Ticket lifecycle/state policies must remain in core/workflows.
    This gateway only normalizes inbound payloads, maps sessions, and routes egress.
    """

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
            ack_metadata = dict(inbound.metadata)
            ack_metadata["skip_delivery"] = True
            outbound = OutboundEnvelope(
                channel=inbound.channel,
                session_id=inbound.session_id,
                body=f"[gateway-ack] {inbound.message_text}",
                metadata=ack_metadata,
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
            status = self._map_error_status(error.code)
            if status == "duplicate_ignored":
                return {
                    "status": status,
                    "trace_id": trace_id,
                    "error": error.to_dict(),
                }
            return {
                "status": status,
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

    def send_outbound(
        self,
        *,
        channel: str,
        session_id: str,
        body: str,
        metadata: dict[str, Any] | None = None,
        retries: int = 2,
    ) -> dict[str, object]:
        outbound = OutboundEnvelope(
            channel=channel,
            session_id=session_id,
            body=body,
            metadata=dict(metadata or {}),
        )
        return self._outbound_sender.send(outbound, retries=retries)

    @staticmethod
    def _map_error_status(code: str) -> str:
        if code == "duplicate_webhook":
            return "duplicate_ignored"
        if code.startswith("missing_") or code.startswith("invalid_"):
            return "invalid_payload"
        return "error"
