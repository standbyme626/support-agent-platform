from __future__ import annotations

import argparse
import json

from scripts.run_acceptance import build_runtime
from scripts.wecom_bridge_server import process_wecom_message


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay WeCom dispatch bridge flow")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--sender-id", required=True, help="WeCom sender user id")
    parser.add_argument("--chat-id", required=True, help="WeCom group/chat id")
    parser.add_argument("--text", required=True, help="Inbound message text")
    parser.add_argument("--trace-id", default="trace-wecom-dispatch-replay")
    parser.add_argument("--msg-id", default="msg-wecom-dispatch-replay")
    parser.add_argument("--show-trace-limit", type=int, default=30)
    args = parser.parse_args()

    runtime = build_runtime(args.env)
    result = process_wecom_message(
        runtime,
        {
            "msgid": args.msg_id,
            "chatid": args.chat_id,
            "chattype": "group",
            "sender_id": args.sender_id,
            "text": args.text,
            "req_id": args.trace_id,
        },
    )
    trace_events = runtime.trace_logger.query_by_trace(args.trace_id, limit=args.show_trace_limit)
    print(
        json.dumps(
            {
                "bridge_result": result.as_json(),
                "trace_events": trace_events,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
