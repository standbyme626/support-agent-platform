from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from channel_adapters.base import BaseChannelAdapter, ChannelAdapterError
from storage.models import InboundEnvelope, OutboundEnvelope


@dataclass(frozen=True)
class _WeComSendTarget:
    corp_id: str
    corp_secret: str
    agent_id: str
    user_id: str
    group_id: str
    use_group_api: bool


class WeComAdapter(BaseChannelAdapter):
    channel = "wecom"
    _DEFAULT_ALLOWED_SOURCES: ClassVar[set[str]] = {"wecom", "wecom_bridge", "openclaw_replay"}
    _DEFAULT_API_BASE_URL: ClassVar[str] = "https://qyapi.weixin.qq.com"
    _RETRYABLE_ERRCODES: ClassVar[set[int]] = {-1, 40014, 42001, 42007, 45009}

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._cached_access_token: str | None = None
        self._cached_access_token_expire_at: float = 0.0

    def verify_inbound(self, payload: dict[str, Any]) -> None:
        signature = payload.get("signature") or payload.get("msg_signature")
        if not signature:
            return

        source = self._extract_source(payload)
        allowed_sources = self._resolve_allowed_sources(payload)
        if bool(payload.get("require_source_validation")) and not source:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_source",
                message="wecom source validation requires source",
            )
        if source and allowed_sources and source not in allowed_sources:
            raise ChannelAdapterError(
                channel=self.channel,
                code="invalid_source",
                message=f"wecom source is not trusted: {source}",
                context={"allowed_sources": sorted(allowed_sources)},
            )

        secret = str(payload.get("secret") or "")
        timestamp = str(payload.get("timestamp") or "")
        nonce = str(payload.get("nonce") or "")
        if not secret or not timestamp or not nonce:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_signature_fields",
                message="wecom signature verification requires secret/timestamp/nonce",
            )

        try:
            ts_int = int(timestamp)
        except ValueError as exc:
            raise ChannelAdapterError(
                channel=self.channel,
                code="invalid_timestamp",
                message="invalid wecom timestamp",
            ) from exc

        if abs(int(time.time()) - ts_int) > 300:
            raise ChannelAdapterError(
                channel=self.channel,
                code="replay_window_exceeded",
                message="wecom timestamp exceeds replay window",
            )

        expected = hmac.new(
            secret.encode(),
            f"{timestamp}:{nonce}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(str(signature), expected):
            raise ChannelAdapterError(
                channel=self.channel,
                code="invalid_signature",
                message="wecom signature mismatch",
            )

    def _extract_source(self, payload: dict[str, Any]) -> str | None:
        for key in ("source", "source_name", "origin"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip().lower()
            if text:
                return text
        return None

    def _resolve_allowed_sources(self, payload: dict[str, Any]) -> set[str]:
        raw = payload.get("allowed_sources")
        if isinstance(raw, str):
            values = [item.strip().lower() for item in raw.split(",") if item.strip()]
            if values:
                return set(values)
        if isinstance(raw, list):
            values = [str(item).strip().lower() for item in raw if str(item).strip()]
            if values:
                return set(values)
        return set(self._DEFAULT_ALLOWED_SOURCES)

    def idempotency_key(self, payload: dict[str, Any]) -> str | None:
        msg_id = payload.get("MsgId")
        if msg_id:
            return f"{self.channel}:{msg_id}"
        session_id = payload.get("session_id") or payload.get("FromUserName")
        create_time = payload.get("CreateTime")
        if session_id and create_time:
            return f"{self.channel}:{session_id}:{create_time}"
        return None

    def build_inbound(self, payload: dict[str, Any]) -> InboundEnvelope:
        msg_id = payload.get("MsgId")
        session_id = str(payload.get("session_id") or payload.get("FromUserName") or "")
        message_text = str(payload.get("Content") or payload.get("text") or "")
        if not session_id:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_session_id",
                message="wecom inbound payload missing FromUserName/session_id",
                context={"required_fields": ["FromUserName", "session_id"]},
            )
        if not message_text:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_message_text",
                message="wecom inbound payload missing Content/text",
                context={"required_fields": ["Content", "text"]},
            )
        inbox = str(payload.get("inbox") or f"{self.channel}.default")
        external_message_id = msg_id or payload.get("CreateTime")
        key_source = "MsgId" if msg_id else "FromUserName+CreateTime"
        metadata = {
            "msg_id": msg_id,
            "agent_id": payload.get("AgentID"),
            "create_time": payload.get("CreateTime"),
            "inbox": inbox,
            "conversation_id": session_id,
            "external_message_id": external_message_id,
            "contract_version": "wecom.v2",
            "idempotency_key_source": key_source,
            "source": self._extract_source(payload),
        }
        return InboundEnvelope(
            channel=self.channel,
            session_id=session_id,
            message_text=message_text,
            metadata=metadata,
        )

    def build_outbound(self, envelope: OutboundEnvelope) -> dict[str, object]:
        return {
            "touser": envelope.session_id,
            "msgtype": "text",
            "text": {"content": envelope.body},
            "metadata": envelope.metadata,
        }

    def deliver_outbound(
        self,
        *,
        outbound: OutboundEnvelope,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if not _truthy(os.getenv("WECOM_APP_API_ENABLED"), default=False):
            return {
                "mode": "render_only",
                "reason": "wecom_app_api_disabled",
            }

        target = self._resolve_send_target(outbound=outbound, payload=payload)
        access_token = self._get_access_token(
            corp_id=target.corp_id,
            corp_secret=target.corp_secret,
        )

        if target.use_group_api:
            response = self._request_json(
                method="POST",
                path="/cgi-bin/appchat/send",
                params={"access_token": access_token},
                json_body={
                    "chatid": target.group_id,
                    "msgtype": "text",
                    "text": {"content": outbound.body},
                    "safe": 0,
                },
            )
            action = "appchat_send"
        else:
            response = self._request_json(
                method="POST",
                path="/cgi-bin/message/send",
                params={"access_token": access_token},
                json_body={
                    "touser": target.user_id,
                    "msgtype": "text",
                    "agentid": target.agent_id,
                    "text": {"content": outbound.body},
                    "safe": 0,
                },
            )
            action = "message_send"

        errcode = _as_int(response.get("errcode"), default=-1)
        if errcode != 0:
            raise self._build_wecom_api_error(action=action, response=response)

        return {
            "mode": "api_sent",
            "action": action,
            "errcode": errcode,
            "errmsg": str(response.get("errmsg") or "ok"),
            "invaliduser": str(response.get("invaliduser") or ""),
            "invalidparty": str(response.get("invalidparty") or ""),
            "invalidtag": str(response.get("invalidtag") or ""),
        }

    def _resolve_send_target(
        self,
        *,
        outbound: OutboundEnvelope,
        payload: dict[str, object],
    ) -> _WeComSendTarget:
        metadata = dict(outbound.metadata or {})
        session_user, session_group = self._parse_session_id(outbound.session_id)
        target_group_id = str(metadata.get("target_group_id") or session_group or "").strip()
        outbound_type = str(metadata.get("outbound_type") or "").strip()
        force_group = _truthy(metadata.get("force_group_send"), default=False)
        use_group_api = bool(target_group_id) and (force_group or outbound_type == "collab_dispatch")

        corp_id = (
            os.getenv("WECOM_CORP_ID")
            or os.getenv("WECOM_BOT_ID")
            or os.getenv("WECOM_CORPID")
            or ""
        ).strip()
        corp_secret = (
            os.getenv("WECOM_CORP_SECRET")
            or os.getenv("WECOM_AGENT_SECRET")
            or os.getenv("WECOM_BOT_SECRET")
            or ""
        ).strip()
        if not corp_id or not corp_secret:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_wecom_credentials",
                message="wecom outbound requires WECOM_CORP_ID/WECOM_BOT_ID and WECOM_AGENT_SECRET",
                retryable=False,
            )

        agent_id = str(metadata.get("agent_id") or os.getenv("WECOM_AGENT_ID") or "").strip()
        user_id = str(metadata.get("target_user_id") or session_user or payload.get("touser") or "").strip()
        if use_group_api and not target_group_id:
            raise ChannelAdapterError(
                channel=self.channel,
                code="missing_target_group_id",
                message="wecom group send requires target_group_id",
                retryable=False,
            )
        if not use_group_api:
            if not user_id:
                raise ChannelAdapterError(
                    channel=self.channel,
                    code="missing_target_user_id",
                    message="wecom message send requires user target",
                    retryable=False,
                )
            if not agent_id:
                raise ChannelAdapterError(
                    channel=self.channel,
                    code="missing_wecom_agent_id",
                    message="wecom message send requires WECOM_AGENT_ID or outbound metadata.agent_id",
                    retryable=False,
                )

        return _WeComSendTarget(
            corp_id=corp_id,
            corp_secret=corp_secret,
            agent_id=agent_id,
            user_id=user_id,
            group_id=target_group_id,
            use_group_api=use_group_api,
        )

    def _get_access_token(self, *, corp_id: str, corp_secret: str) -> str:
        now = time.time()
        if self._cached_access_token and now < (self._cached_access_token_expire_at - 30):
            return self._cached_access_token

        response = self._request_json(
            method="GET",
            path="/cgi-bin/gettoken",
            params={"corpid": corp_id, "corpsecret": corp_secret},
        )
        errcode = _as_int(response.get("errcode"), default=-1)
        if errcode != 0:
            raise self._build_wecom_api_error(action="gettoken", response=response)
        access_token = str(response.get("access_token") or "").strip()
        if not access_token:
            raise ChannelAdapterError(
                channel=self.channel,
                code="wecom_missing_access_token",
                message="wecom gettoken succeeded but access_token is empty",
                retryable=True,
            )
        expires_in = max(60, _as_int(response.get("expires_in"), default=7200))
        self._cached_access_token = access_token
        self._cached_access_token_expire_at = now + expires_in
        return access_token

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, str],
        json_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        base_url = os.getenv("WECOM_API_BASE_URL", self._DEFAULT_API_BASE_URL).rstrip("/")
        url = f"{base_url}{path}"
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
                trust_env=False,
            ) as client:
                if method == "GET":
                    response = client.get(url, params=params)
                else:
                    response = client.post(url, params=params, json=json_body)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as exc:
            raise ChannelAdapterError(
                channel=self.channel,
                code="wecom_http_request_failed",
                message=f"wecom request failed: {exc}",
                retryable=True,
                context={"path": path, "method": method},
            ) from exc

        if response.status_code >= 500:
            raise ChannelAdapterError(
                channel=self.channel,
                code="wecom_http_server_error",
                message=f"wecom api status={response.status_code}",
                retryable=True,
                context={"path": path, "method": method, "status_code": response.status_code},
            )
        if response.status_code >= 400:
            raise ChannelAdapterError(
                channel=self.channel,
                code="wecom_http_client_error",
                message=f"wecom api status={response.status_code}",
                retryable=response.status_code in {408, 429},
                context={"path": path, "method": method, "status_code": response.status_code},
            )

        try:
            parsed = response.json()
        except ValueError as exc:
            raise ChannelAdapterError(
                channel=self.channel,
                code="wecom_invalid_json_response",
                message="wecom api returned invalid json",
                retryable=False,
                context={"path": path, "method": method},
            ) from exc
        if not isinstance(parsed, dict):
            raise ChannelAdapterError(
                channel=self.channel,
                code="wecom_invalid_response_type",
                message="wecom api response is not json object",
                retryable=False,
                context={"path": path, "method": method},
            )
        return parsed

    def _build_wecom_api_error(self, *, action: str, response: dict[str, object]) -> ChannelAdapterError:
        errcode = _as_int(response.get("errcode"), default=-1)
        errmsg = str(response.get("errmsg") or "unknown error")
        return ChannelAdapterError(
            channel=self.channel,
            code=f"wecom_{action}_failed",
            message=f"wecom {action} failed: errcode={errcode} errmsg={errmsg}",
            retryable=errcode in self._RETRYABLE_ERRCODES,
            context={"action": action, "errcode": errcode, "errmsg": errmsg},
        )

    def _parse_session_id(self, session_id: str) -> tuple[str, str]:
        normalized = str(session_id or "").strip()
        if normalized.startswith("dm:"):
            return normalized[3:].strip(), ""
        if normalized.startswith("group:") and ":user:" in normalized:
            group_part = normalized.split(":", 2)[1]
            user_part = normalized.split(":user:", 1)[1]
            return user_part.strip(), group_part.strip()
        return normalized, ""


def _truthy(raw: object, *, default: bool) -> bool:
    if raw is None:
        return default
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(raw: object, *, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(str(raw))
    except ValueError:
        return default
