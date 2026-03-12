from __future__ import annotations

from dataclasses import dataclass

from channel_adapters.base import ChannelAdapterError
from core.trace_logger import JsonTraceLogger

from .session_mapper import SessionMapper


@dataclass(frozen=True)
class ReplayDecision:
    channel: str
    session_id: str
    idempotency_key: str | None
    accepted: bool
    replay_count: int
    reason: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            "channel": self.channel,
            "session_id": self.session_id,
            "idempotency_key": self.idempotency_key,
            "accepted": self.accepted,
            "replay_count": self.replay_count,
            "reason": self.reason,
        }


class ReplayGuard:
    """Session-scoped replay guard on top of SessionMapper metadata."""

    def __init__(self, *, session_mapper: SessionMapper, trace_logger: JsonTraceLogger) -> None:
        self._session_mapper = session_mapper
        self._trace_logger = trace_logger

    def evaluate(
        self,
        *,
        channel: str,
        session_id: str,
        idempotency_key: str | None,
        trace_id: str | None,
    ) -> ReplayDecision:
        if not idempotency_key:
            return ReplayDecision(
                channel=channel,
                session_id=session_id,
                idempotency_key=None,
                accepted=True,
                replay_count=0,
                reason="missing_idempotency_key",
            )

        accepted, binding = self._session_mapper.record_idempotency_key(
            session_id=session_id,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            channel=channel,
        )
        replay_count = int(binding.metadata.get("replay_count", 0))
        decision = ReplayDecision(
            channel=channel,
            session_id=session_id,
            idempotency_key=idempotency_key,
            accepted=accepted,
            replay_count=replay_count,
            reason=("duplicate_webhook" if not accepted else None),
        )
        self._trace_logger.log(
            "ingress_replay_guard",
            decision.to_payload(),
            trace_id=trace_id or None,
            ticket_id=binding.ticket_id,
            session_id=session_id,
        )
        return decision

    def enforce(self, *, decision: ReplayDecision) -> None:
        if decision.accepted:
            return
        raise ChannelAdapterError(
            channel=decision.channel,
            code="duplicate_webhook",
            message=f"duplicate inbound webhook: {decision.idempotency_key}",
            retryable=False,
            context={"idempotency_key": decision.idempotency_key},
        )
