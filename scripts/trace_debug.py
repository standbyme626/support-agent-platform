from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config
from core.trace_logger import JsonTraceLogger

_RETRY_OBSERVED_EVENTS = {"egress_failed", "egress_retry_scheduled", "egress_retry_exhausted"}
_SIGNATURE_EVENTS = {"signature_validated", "signature_rejected"}
_REPLAY_EVENTS = {"ingress_replay_guard"}


def debug_trace(
    *,
    environment: str | None,
    trace_id: str | None,
    ticket_id: str | None,
    session_id: str | None,
    limit: int,
    include_reliability: bool = False,
) -> list[dict[str, object]] | dict[str, object]:
    app_config = load_app_config(environment)
    logger = JsonTraceLogger(Path(app_config.gateway.log_path))

    events: list[dict[str, object]]
    if trace_id:
        events = logger.query_by_trace(trace_id, limit=limit)
    elif ticket_id:
        events = logger.query_by_ticket(ticket_id, limit=limit)
    elif session_id:
        events = logger.query_by_session(session_id, limit=limit)
    else:
        events = logger.read_recent(limit=limit)

    if not include_reliability:
        return events
    return {
        "events": events,
        "reliability": _summarize_reliability(events),
    }


def _summarize_reliability(events: list[dict[str, object]]) -> dict[str, object]:
    retry_events = [
        event
        for event in events
        if str(event.get("event_type") or "") in _RETRY_OBSERVED_EVENTS
    ]
    retry_failures = [
        event for event in retry_events if str(event.get("event_type") or "") == "egress_failed"
    ]
    retry_observed_count = 0
    for event in retry_failures:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        retry_payload = payload.get("retry")
        if not isinstance(retry_payload, dict):
            continue
        if retry_payload.get("classification"):
            retry_observed_count += 1
    signature_events = [
        event for event in events if str(event.get("event_type") or "") in _SIGNATURE_EVENTS
    ]
    replay_events = [
        event for event in events if str(event.get("event_type") or "") in _REPLAY_EVENTS
    ]
    duplicate_replays = 0
    for event in replay_events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        accepted = payload.get("accepted")
        if accepted is False:
            duplicate_replays += 1

    retry_coverage = 1.0
    if retry_failures:
        retry_coverage = retry_observed_count / len(retry_failures)

    return {
        "total_events": len(events),
        "retry": {
            "failed_count": len(retry_failures),
            "observed_count": retry_observed_count,
            "observability_rate": round(retry_coverage, 4),
        },
        "signature": {
            "total": len(signature_events),
            "rejected": sum(
                1
                for event in signature_events
                if str(event.get("event_type") or "") == "signature_rejected"
            ),
        },
        "replay": {
            "total": len(replay_events),
            "duplicate_count": duplicate_replays,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Query trace logs by trace/session/ticket")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--ticket-id", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--include-reliability",
        action="store_true",
        help="Include replay/signature/retry reliability summary",
    )
    args = parser.parse_args()

    events = debug_trace(
        environment=args.env,
        trace_id=args.trace_id,
        ticket_id=args.ticket_id,
        session_id=args.session_id,
        limit=args.limit,
        include_reliability=args.include_reliability,
    )
    print(json.dumps(events, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
