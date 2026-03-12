from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time

from config import load_app_config
from openclaw_adapter.bindings import build_default_bindings
from openclaw_adapter.gateway import OpenClawGateway


def replay_event(
    *,
    environment: str | None,
    channel: str,
    session_id: str,
    text: str,
    trace_id: str | None,
    replay_count: int = 1,
    with_signature: bool = False,
    signature_secret: str | None = None,
    source: str = "openclaw_replay",
    message_id: str = "replay-msg",
) -> dict[str, object]:
    app_config = load_app_config(environment)
    bindings = build_default_bindings(app_config)
    gateway = OpenClawGateway(bindings)

    results: list[dict[str, object]] = []
    for index in range(replay_count):
        payload = _build_payload(
            channel=channel,
            session_id=session_id,
            text=text,
            trace_id=trace_id,
            source=source,
            message_id=message_id,
            with_signature=with_signature,
            signature_secret=signature_secret,
            replay_index=index,
        )
        results.append(gateway.receive(channel, payload))

    if replay_count == 1:
        return results[0]
    duplicate_count = sum(
        1 for item in results if str(item.get("status") or "") == "duplicate_ignored"
    )
    return {
        "count": replay_count,
        "duplicate_count": duplicate_count,
        "accepted_count": replay_count - duplicate_count,
        "results": results,
    }


def _build_payload(
    *,
    channel: str,
    session_id: str,
    text: str,
    trace_id: str | None,
    source: str,
    message_id: str,
    with_signature: bool,
    signature_secret: str | None,
    replay_index: int,
) -> dict[str, object]:
    if channel == "telegram":
        return {
            "trace_id": trace_id,
            "source": source,
            "message": {"chat": {"id": session_id, "username": "replay"}, "text": text},
        }

    if channel == "wecom":
        payload: dict[str, object] = {
            "trace_id": trace_id,
            "source": source,
            "FromUserName": session_id,
            "Content": text,
            "MsgId": message_id,
        }
        if with_signature:
            secret = signature_secret or "replay-secret"
            timestamp = str(int(time.time()))
            nonce = f"replay-{replay_index}"
            signature = hmac.new(
                secret.encode(),
                f"{timestamp}:{nonce}".encode(),
                hashlib.sha256,
            ).hexdigest()
            payload.update(
                {
                    "signature": signature,
                    "secret": secret,
                    "timestamp": timestamp,
                    "nonce": nonce,
                    "require_source_validation": True,
                }
            )
        return payload

    if channel == "feishu":
        return {
            "trace_id": trace_id,
            "source": source,
            "event": {
                "sender": {"sender_id": {"open_id": session_id}},
                "message": {"text": text, "message_id": message_id},
            },
            "tenant_key": "replay-tenant",
        }

    raise ValueError(f"Unsupported channel: {channel}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay one ingress event to gateway")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--channel", required=True, choices=["telegram", "feishu", "wecom"])
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--with-signature", action="store_true")
    parser.add_argument("--signature-secret", default=None)
    parser.add_argument("--source", default="openclaw_replay")
    parser.add_argument("--message-id", default="replay-msg")
    args = parser.parse_args()

    result = replay_event(
        environment=args.env,
        channel=args.channel,
        session_id=args.session_id,
        text=args.text,
        trace_id=args.trace_id,
        replay_count=max(1, args.repeat),
        with_signature=bool(args.with_signature),
        signature_secret=args.signature_secret,
        source=args.source,
        message_id=args.message_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
