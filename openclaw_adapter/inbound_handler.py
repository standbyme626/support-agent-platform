from __future__ import annotations

from dataclasses import replace
from typing import Any

from channel_adapters.base import ChannelAdapterError
from core.disambiguation import detect_session_control
from core.trace_logger import new_trace_id
from storage.models import InboundEnvelope

from .bindings import GatewayBindings
from .replay_guard import ReplayGuard
from .signature_validator import SignatureValidationResult, SignatureValidator


class InboundHandler:
    """Translate raw channel payload to normalized ingress envelope."""

    def __init__(self, bindings: GatewayBindings) -> None:
        self._bindings = bindings
        self._signature_validator = SignatureValidator()
        self._replay_guard = ReplayGuard(
            session_mapper=bindings.session_mapper,
            trace_logger=bindings.trace_logger,
        )

    def handle(self, channel: str, payload: dict[str, Any]) -> InboundEnvelope:
        adapter = self._bindings.channel_router.resolve(channel)
        trace_hint = str(payload.get("trace_id") or "")
        session_hint = self._session_hint(payload)
        try:
            validation = self._signature_validator.validate(
                channel=channel,
                payload=payload,
                adapter=adapter,
            )
        except ChannelAdapterError as error:
            self._audit_signature_rejected(
                channel=channel,
                error=error,
                trace_id=trace_hint or None,
                session_id=session_hint,
            )
            raise
        self._audit_signature_validated(
            result=validation,
            trace_id=trace_hint or None,
            session_id=session_hint,
        )

        inbound = adapter.build_inbound(payload)
        trace_id = str(
            payload.get("trace_id") or inbound.metadata.get("trace_id") or new_trace_id()
        )
        inbox = str(inbound.metadata.get("inbox") or f"{inbound.channel}.default")
        idempotency_key = (
            adapter.idempotency_key(payload)
            or str(inbound.metadata.get("external_message_id") or "")
            or None
        )

        binding = self._bindings.session_mapper.get_or_create(
            session_id=inbound.session_id,
            metadata={
                "channel": inbound.channel,
                "trace_id": trace_id,
                "inbox": inbox,
                **inbound.metadata,
            },
        )

        replay_decision = self._replay_guard.evaluate(
            channel=inbound.channel,
            session_id=inbound.session_id,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
        )
        self._replay_guard.enforce(decision=replay_decision)
        refreshed_binding = self._bindings.session_mapper.get(inbound.session_id)
        if refreshed_binding is not None:
            binding = refreshed_binding

        raw_session_context = binding.metadata.get("session_context")
        session_context = dict(raw_session_context) if isinstance(raw_session_context, dict) else {}
        active_ticket_id = (
            str(session_context.get("active_ticket_id") or binding.ticket_id or "").strip() or None
        )
        recent_ticket_ids = [
            str(item).strip()
            for item in session_context.get("recent_ticket_ids", [])
            if str(item).strip()
        ]
        if active_ticket_id:
            recent_ticket_ids = [item for item in recent_ticket_ids if item != active_ticket_id]
        normalized_session_context = {
            **session_context,
            "active_ticket_id": active_ticket_id,
            "recent_ticket_ids": recent_ticket_ids,
        }
        session_control = detect_session_control(inbound.message_text)
        if session_control is not None:
            normalized_session_context["session_control_action"] = session_control.action
            normalized_session_context["session_control_reason"] = session_control.reason
            normalized_session_context["session_control_source"] = session_control.source
            normalized_session_context["session_control_priority"] = session_control.priority

        passthrough_metadata = {
            **inbound.metadata,
            "trace_id": trace_id,
            "inbox": inbox,
            "thread_id": binding.thread_id,
            "ticket_id": active_ticket_id,
            "idempotency_key": idempotency_key,
            "replay_count": int(binding.metadata.get("replay_count", 0)),
            "active_ticket_id": active_ticket_id,
            "recent_ticket_ids": recent_ticket_ids,
            "session_context": normalized_session_context,
        }
        if session_control is not None:
            passthrough_metadata["session_control_action"] = session_control.action
            passthrough_metadata["session_control_reason"] = session_control.reason
            passthrough_metadata["session_control_source"] = session_control.source
            passthrough_metadata["session_control_priority"] = session_control.priority
        enriched_inbound = replace(inbound, metadata=passthrough_metadata)

        self._bindings.trace_logger.log(
            "ingress_normalized",
            {
                "channel": inbound.channel,
                "session_id": inbound.session_id,
                "thread_id": binding.thread_id,
                "ticket_id": binding.ticket_id,
                "inbox": inbox,
                "idempotency_key": idempotency_key,
                "replay_count": int(binding.metadata.get("replay_count", 0)),
            },
            trace_id=trace_id,
            ticket_id=binding.ticket_id,
            session_id=inbound.session_id,
        )
        return enriched_inbound

    @staticmethod
    def _session_hint(payload: dict[str, Any]) -> str | None:
        for key in ("session_id", "FromUserName"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _audit_signature_validated(
        self,
        *,
        result: SignatureValidationResult,
        trace_id: str | None,
        session_id: str | None,
    ) -> None:
        if not result.signature_checked and not result.source_checked:
            return
        self._bindings.trace_logger.log(
            "signature_validated",
            result.to_payload(),
            trace_id=trace_id,
            session_id=session_id,
        )

    def _audit_signature_rejected(
        self,
        *,
        channel: str,
        error: ChannelAdapterError,
        trace_id: str | None,
        session_id: str | None,
    ) -> None:
        self._bindings.trace_logger.log(
            "signature_rejected",
            {
                "channel": channel,
                "error": error.to_dict(),
            },
            trace_id=trace_id,
            session_id=session_id,
        )
