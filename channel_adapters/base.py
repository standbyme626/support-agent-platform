from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from storage.models import InboundEnvelope, OutboundEnvelope


class ChannelAdapterError(RuntimeError):
    def __init__(
        self,
        *,
        channel: str,
        code: str,
        message: str,
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.channel = channel
        self.code = code
        self.retryable = retryable
        self.context = context or {}

    def to_dict(self) -> dict[str, object]:
        return {
            "channel": self.channel,
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
            "context": self.context,
        }


class BaseChannelAdapter(ABC):
    channel: str

    @abstractmethod
    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        """Normalize raw channel payload into an inbound envelope.

        Adapters only shape ingress/session metadata and must not apply business rules.
        """

    @abstractmethod
    def build_outbound(self, envelope: OutboundEnvelope) -> dict[str, object]:
        """Render normalized outbound envelope into channel payload."""

    def verify_inbound(self, payload: dict[str, Any]) -> None:
        """Optionally validate signature/replay guard metadata on raw payload."""
        return None

    def idempotency_key(self, payload: dict[str, Any]) -> str | None:
        """Return a stable webhook id for replay protection."""
        return None
