from __future__ import annotations

import argparse
import json

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
) -> dict[str, object]:
    app_config = load_app_config(environment)
    bindings = build_default_bindings(app_config)
    gateway = OpenClawGateway(bindings)

    payload = _build_payload(channel=channel, session_id=session_id, text=text, trace_id=trace_id)
    return gateway.receive(channel, payload)


def _build_payload(
    *,
    channel: str,
    session_id: str,
    text: str,
    trace_id: str | None,
) -> dict[str, object]:
    if channel == "telegram":
        return {
            "trace_id": trace_id,
            "message": {"chat": {"id": session_id, "username": "replay"}, "text": text},
        }

    if channel == "wecom":
        return {
            "trace_id": trace_id,
            "FromUserName": session_id,
            "Content": text,
            "MsgId": "replay-msg",
        }

    if channel == "feishu":
        return {
            "trace_id": trace_id,
            "event": {
                "sender": {"sender_id": {"open_id": session_id}},
                "message": {"text": text, "message_id": "replay-msg"},
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
    args = parser.parse_args()

    result = replay_event(
        environment=args.env,
        channel=args.channel,
        session_id=args.session_id,
        text=args.text,
        trace_id=args.trace_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
