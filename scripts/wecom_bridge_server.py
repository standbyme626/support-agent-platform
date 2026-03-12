from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol
from urllib.parse import urlparse

from scripts.run_acceptance import build_runtime
from storage.models import InboundEnvelope

DEFAULT_REPLY_ON_ERROR = "系统繁忙，请稍后再试。"
DEFAULT_BRIDGE_PATH = "/wecom/process"


@dataclass(frozen=True)
class BridgeResult:
    handled: bool
    reply_text: str
    status: str
    ticket_id: str | None = None
    ticket_action: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "handled": self.handled,
            "reply_text": self.reply_text,
            "status": self.status,
            "ticket_id": self.ticket_id,
            "ticket_action": self.ticket_action,
        }


class _GatewayLike(Protocol):
    def receive(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class _IntakeLike(Protocol):
    def run(self, envelope: InboundEnvelope) -> Any: ...


class _RuntimeLike(Protocol):
    @property
    def gateway(self) -> _GatewayLike: ...

    @property
    def intake_workflow(self) -> _IntakeLike: ...


def process_wecom_message(runtime: _RuntimeLike, payload: dict[str, Any]) -> BridgeResult:
    text = _pick_text(payload)
    sender_id = _pick_string(payload, "sender_id", "FromUserName")
    chat_id = _pick_string(payload, "chatid", "ChatId") or sender_id
    chat_type = (_pick_string(payload, "chattype", "ChatType") or "single").lower()
    msg_id = _pick_string(payload, "msgid", "MsgId")
    req_id = _pick_string(payload, "req_id", "ReqId", "trace_id") or msg_id or f"trace-{int(time.time())}"

    if not text:
        return BridgeResult(handled=True, reply_text="", status="ignored_empty")

    if not sender_id:
        return BridgeResult(
            handled=True,
            reply_text=DEFAULT_REPLY_ON_ERROR,
            status="invalid_sender",
        )

    session_id = _compose_session_id(sender_id=sender_id, chat_id=chat_id, chat_type=chat_type)
    ingress_payload = {
        "trace_id": req_id,
        "session_id": session_id,
        "FromUserName": sender_id,
        "Content": text,
        "MsgId": msg_id,
        "CreateTime": str(int(time.time())),
        "inbox": "wecom.default",
    }
    ingress_result = runtime.gateway.receive("wecom", ingress_payload)
    ingress_status = str(ingress_result.get("status") or "error")
    if ingress_status == "duplicate_ignored":
        return BridgeResult(handled=True, reply_text="", status=ingress_status)
    if ingress_status != "ok":
        return BridgeResult(handled=True, reply_text=DEFAULT_REPLY_ON_ERROR, status=ingress_status)

    inbound_payload = ingress_result.get("inbound")
    if not isinstance(inbound_payload, dict):
        return BridgeResult(
            handled=True,
            reply_text=DEFAULT_REPLY_ON_ERROR,
            status="invalid_inbound",
        )

    envelope = InboundEnvelope(
        channel=str(inbound_payload.get("channel") or "wecom"),
        session_id=str(inbound_payload.get("session_id") or session_id),
        message_text=str(inbound_payload.get("message_text") or text),
        metadata=dict(inbound_payload.get("metadata") or {}),
    )
    intake = runtime.intake_workflow.run(envelope)
    return BridgeResult(
        handled=True,
        reply_text=intake.reply_text,
        status="ok",
        ticket_id=intake.ticket_id,
        ticket_action=intake.ticket_action,
    )


def _compose_session_id(*, sender_id: str, chat_id: str, chat_type: str) -> str:
    if chat_type == "group":
        return f"group:{chat_id}:user:{sender_id}"
    return f"dm:{sender_id}"


def _pick_string(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _pick_text(payload: dict[str, Any]) -> str:
    for key in ("text", "Content"):
        value = payload.get(key)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
        if isinstance(value, dict):
            nested = value.get("content")
            if nested is not None:
                text = str(nested).strip()
                if text:
                    return text
    return ""


def _build_handler(*, runtime: _RuntimeLike, path: str) -> type[BaseHTTPRequestHandler]:
    route_path = path

    class BridgeHandler(BaseHTTPRequestHandler):
        server_version = "SupportAgentWeComBridge/1.0"

        def do_POST(self) -> None:
            if urlparse(self.path).path != route_path:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            try:
                body = self._read_json_body()
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            try:
                result = process_wecom_message(runtime, body)
            except Exception:
                result = BridgeResult(
                    handled=True,
                    reply_text=DEFAULT_REPLY_ON_ERROR,
                    status="runtime_error",
                )
            self._write_json(HTTPStatus.OK, result.as_json())

        def do_GET(self) -> None:
            if urlparse(self.path).path != "/healthz":
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._write_json(HTTPStatus.OK, {"status": "ok"})

        def _read_json_body(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("missing content-length")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ValueError("invalid content-length") from exc
            if length <= 0:
                raise ValueError("empty body")
            data = self.rfile.read(length)
            try:
                decoded = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("invalid json") from exc
            if not isinstance(decoded, dict):
                raise ValueError("json body must be object")
            return decoded

        def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    return BridgeHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WeCom -> workflow bridge server")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument(
        "--host",
        default=os.getenv("WECOM_BRIDGE_HOST", "127.0.0.1"),
        help="HTTP bind host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WECOM_BRIDGE_PORT", "18081")),
        help="HTTP bind port",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("WECOM_BRIDGE_PATH", DEFAULT_BRIDGE_PATH),
        help="Bridge POST path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = build_runtime(args.env)
    handler = _build_handler(runtime=runtime, path=args.path)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "status": "starting",
                "host": args.host,
                "port": args.port,
                "path": args.path,
                "healthz": "/healthz",
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
