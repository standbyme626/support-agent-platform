from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config
from core.trace_logger import JsonTraceLogger


def debug_trace(
    *,
    environment: str | None,
    trace_id: str | None,
    ticket_id: str | None,
    session_id: str | None,
    limit: int,
) -> list[dict[str, object]]:
    app_config = load_app_config(environment)
    logger = JsonTraceLogger(Path(app_config.gateway.log_path))

    if trace_id:
        return logger.query_by_trace(trace_id, limit=limit)
    if ticket_id:
        return logger.query_by_ticket(ticket_id, limit=limit)
    if session_id:
        return logger.query_by_session(session_id, limit=limit)
    return logger.read_recent(limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser(description="Query trace logs by trace/session/ticket")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--ticket-id", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    events = debug_trace(
        environment=args.env,
        trace_id=args.trace_id,
        ticket_id=args.ticket_id,
        session_id=args.session_id,
        limit=args.limit,
    )
    print(json.dumps(events, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
