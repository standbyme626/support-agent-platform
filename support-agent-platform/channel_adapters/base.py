from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from storage.models import InboundEnvelope, OutboundEnvelope


class BaseChannelAdapter(ABC):
    channel: str

    @abstractmethod
    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        """Normalize raw channel payload into an inbound envelope."""

    @abstractmethod
    def build_outbound(self, envelope: OutboundEnvelope) -> dict[str, object]:
        """Render normalized outbound envelope into channel payload."""
