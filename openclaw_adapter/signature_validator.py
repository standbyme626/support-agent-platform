from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from channel_adapters.base import BaseChannelAdapter, ChannelAdapterError

_DEFAULT_ALLOWED_SOURCES: dict[str, set[str]] = {
    "wecom": {"wecom", "wecom_bridge", "openclaw_replay"},
    "feishu": {"feishu", "openclaw_replay"},
    "telegram": {"telegram", "openclaw_replay"},
}


@dataclass(frozen=True)
class SignatureValidationResult:
    channel: str
    signature_checked: bool
    signature_valid: bool
    source_checked: bool
    source_valid: bool
    signature_required: bool
    source: str | None
    reason: str | None

    @property
    def status(self) -> str:
        if self.signature_checked and self.source_checked:
            return "signature_and_source_verified"
        if self.signature_checked:
            return "signature_verified"
        if self.source_checked:
            return "source_verified"
        return "skipped"

    def to_payload(self) -> dict[str, object]:
        return {
            "channel": self.channel,
            "status": self.status,
            "signature_checked": self.signature_checked,
            "signature_valid": self.signature_valid,
            "signature_required": self.signature_required,
            "source_checked": self.source_checked,
            "source_valid": self.source_valid,
            "source": self.source,
            "reason": self.reason,
        }


class SignatureValidator:
    """Channel signature/source gate for ingress payloads."""

    def validate(
        self,
        *,
        channel: str,
        payload: dict[str, Any],
        adapter: BaseChannelAdapter,
    ) -> SignatureValidationResult:
        has_signature = bool(payload.get("signature"))
        signature_required = bool(payload.get("require_signature"))
        source = self._extract_source(payload)

        source_checked = False
        if has_signature or bool(payload.get("require_source_validation")):
            allowed_sources = self._resolve_allowed_sources(channel, payload)
            if allowed_sources:
                source_checked = True
                if not source:
                    raise ChannelAdapterError(
                        channel=channel,
                        code="missing_source",
                        message=f"{channel} source validation requires source",
                        retryable=False,
                    )
                if source not in allowed_sources:
                    raise ChannelAdapterError(
                        channel=channel,
                        code="invalid_source",
                        message=f"{channel} source is not trusted: {source}",
                        retryable=False,
                        context={"allowed_sources": sorted(allowed_sources)},
                    )

        signature_checked = False
        if signature_required and not has_signature:
            raise ChannelAdapterError(
                channel=channel,
                code="missing_signature",
                message=f"{channel} signature is required",
                retryable=False,
            )
        if has_signature:
            signature_checked = True
            adapter.verify_inbound(payload)

        return SignatureValidationResult(
            channel=channel,
            signature_checked=signature_checked,
            signature_valid=True,
            source_checked=source_checked,
            source_valid=True,
            signature_required=signature_required,
            source=source,
            reason=None,
        )

    @staticmethod
    def _extract_source(payload: dict[str, Any]) -> str | None:
        for key in ("source", "source_name", "origin"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @staticmethod
    def _resolve_allowed_sources(channel: str, payload: dict[str, Any]) -> set[str]:
        raw = payload.get("allowed_sources")
        if isinstance(raw, str):
            values = [item.strip() for item in raw.split(",") if item.strip()]
            if values:
                return {item.lower() for item in values}
        if isinstance(raw, list):
            values = [str(item).strip().lower() for item in raw if str(item).strip()]
            if values:
                return set(values)
        return set(_DEFAULT_ALLOWED_SOURCES.get(channel, set()))
