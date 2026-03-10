from __future__ import annotations

from collections.abc import Mapping

from channel_adapters.base import BaseChannelAdapter


class ChannelRouter:
    """Resolve a channel name to its adapter implementation."""

    def __init__(self, adapters: Mapping[str, BaseChannelAdapter]) -> None:
        self._adapters = {channel.lower(): adapter for channel, adapter in adapters.items()}

    @property
    def supported_channels(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters.keys()))

    def resolve(self, channel: str) -> BaseChannelAdapter:
        adapter = self._adapters.get(channel.lower())
        if adapter is None:
            supported = ", ".join(self.supported_channels)
            raise ValueError(f"Unsupported channel '{channel}'. Supported: {supported}")
        return adapter
