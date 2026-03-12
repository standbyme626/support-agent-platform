from __future__ import annotations

from pathlib import Path
from typing import Any

from channel_adapters.base import BaseChannelAdapter, ChannelAdapterError
from core.trace_logger import JsonTraceLogger
from openclaw_adapter.bindings import GatewayBindings
from openclaw_adapter.channel_router import ChannelRouter
from openclaw_adapter.outbound_sender import OutboundSender
from openclaw_adapter.session_mapper import SessionMapper
from storage.models import InboundEnvelope, OutboundEnvelope


class _FlakyAdapter(BaseChannelAdapter):
    channel = "flaky"

    def __init__(self) -> None:
        self._attempt = 0

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:  # pragma: no cover
        return InboundEnvelope(channel=self.channel, session_id="s", message_text="m", metadata={})

    def build_outbound(self, envelope: OutboundEnvelope) -> dict[str, object]:
        self._attempt += 1
        if self._attempt == 1:
            raise ChannelAdapterError(
                channel=self.channel,
                code="temporary_send_failure",
                message="flaky network",
                retryable=True,
            )
        return {"chat_id": envelope.session_id, "text": envelope.body}


def test_outbound_sender_retries_retryable_error(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "trace.log"
    adapter = _FlakyAdapter()
    bindings = GatewayBindings(
        channel_router=ChannelRouter({"flaky": adapter}),
        session_mapper=SessionMapper(sqlite_path),
        trace_logger=JsonTraceLogger(log_path),
    )
    sender = OutboundSender(bindings)
    payload = sender.send(
        OutboundEnvelope(
            channel="flaky",
            session_id="session-1",
            body="hello",
            metadata={"trace_id": "trace-retry"},
        ),
        retries=2,
    )

    assert payload["chat_id"] == "session-1"
    events = bindings.trace_logger.query_by_trace("trace-retry")
    event_types = [item["event_type"] for item in events]
    assert "egress_failed" in event_types
    assert "egress_retry_scheduled" in event_types
    assert "egress_rendered" in event_types
    failed_event = next(item for item in events if item["event_type"] == "egress_failed")
    payload = failed_event["payload"]
    assert isinstance(payload, dict)
    retry_payload = payload.get("retry")
    assert isinstance(retry_payload, dict)
    assert retry_payload.get("classification") == "temporary"
