from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from config import load_app_config
from core.trace_logger import JsonTraceLogger
from openclaw_adapter.session_mapper import SessionMapper
from storage.models import SessionBinding

_SIGNATURE_EVENTS = {"signature_validated", "signature_rejected"}
_REPLAY_EVENT = "ingress_replay_guard"
_RETRY_EVENTS = {"egress_failed", "egress_retry_scheduled", "egress_retry_exhausted"}


def summarize_reliability(
    *,
    recent_events: list[dict[str, Any]],
    session_bindings: list[SessionBinding],
    item_limit: int = 50,
) -> dict[str, object]:
    signature_rows = _summarize_signature_events(recent_events)
    replay_rows, replay_stats = _summarize_replay_events(recent_events, item_limit=item_limit)
    retry_rows, retry_stats = _summarize_retry_events(recent_events, item_limit=item_limit)
    session_rows = _summarize_sessions(session_bindings, item_limit=item_limit)
    return {
        "signature": {
            "items": signature_rows,
            "totals": {
                "checked": sum(_as_int(item.get("checked")) for item in signature_rows),
                "rejected": sum(_as_int(item.get("rejected")) for item in signature_rows),
                "valid": sum(_as_int(item.get("valid")) for item in signature_rows),
            },
        },
        "replays": {
            "items": replay_rows,
            **replay_stats,
        },
        "retries": {
            "items": retry_rows,
            **retry_stats,
        },
        "sessions": {
            "items": session_rows,
            "total": len(session_bindings),
            "bound_to_ticket": sum(1 for binding in session_bindings if binding.ticket_id),
        },
    }


def collect_status(environment: str | None = None) -> dict[str, object]:
    app_config = load_app_config(environment)
    mapper = SessionMapper(Path(app_config.storage.sqlite_path))
    logger = JsonTraceLogger(Path(app_config.gateway.log_path))
    recent_events = logger.read_recent(limit=500)
    session_bindings = mapper.list_bindings(limit=300)
    reliability = summarize_reliability(
        recent_events=recent_events,
        session_bindings=session_bindings,
        item_limit=20,
    )

    return {
        "environment": app_config.environment,
        "gateway": app_config.gateway.name,
        "sqlite_path": str(app_config.storage.sqlite_path),
        "session_bindings": mapper.count(),
        "log_path": str(logger.path),
        "recent_events": recent_events[-5:],
        "reliability": reliability,
    }


def _summarize_signature_events(recent_events: list[dict[str, Any]]) -> list[dict[str, object]]:
    by_channel: dict[str, dict[str, object]] = {}
    for event in recent_events:
        event_type = str(event.get("event_type") or "")
        if event_type not in _SIGNATURE_EVENTS:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        channel = str(payload.get("channel") or "unknown")
        row = by_channel.setdefault(
            channel,
            {
                "channel": channel,
                "checked": 0,
                "valid": 0,
                "rejected": 0,
                "last_checked_at": None,
                "last_error_code": None,
            },
        )
        row["last_checked_at"] = event.get("timestamp")
        if event_type == "signature_rejected":
            row["rejected"] = _as_int(row.get("rejected")) + 1
            error_payload = payload.get("error")
            if isinstance(error_payload, dict):
                row["last_error_code"] = error_payload.get("code")
            continue

        checked = bool(payload.get("signature_checked") or payload.get("source_checked"))
        valid = bool(payload.get("signature_valid") and payload.get("source_valid", True))
        if checked:
            row["checked"] = _as_int(row.get("checked")) + 1
        if checked and valid:
            row["valid"] = _as_int(row.get("valid")) + 1

    rows = [value for _, value in sorted(by_channel.items(), key=lambda item: item[0])]
    return rows


def _summarize_replay_events(
    recent_events: list[dict[str, Any]], *, item_limit: int
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    duplicate_count = 0
    for event in recent_events:
        if str(event.get("event_type") or "") != _REPLAY_EVENT:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        accepted = bool(payload.get("accepted"))
        if not accepted:
            duplicate_count += 1
        rows.append(
            {
                "timestamp": event.get("timestamp"),
                "trace_id": event.get("trace_id"),
                "channel": payload.get("channel"),
                "session_id": payload.get("session_id"),
                "idempotency_key": payload.get("idempotency_key"),
                "accepted": accepted,
                "replay_count": int(payload.get("replay_count") or 0),
            }
        )
    total = len(rows)
    rows = rows[-item_limit:]
    return (
        rows,
        {
            "total": total,
            "duplicate_count": duplicate_count,
            "duplicate_ratio": round((duplicate_count / total), 4) if total else 0.0,
            "non_duplicate_ratio": round(((total - duplicate_count) / total), 4) if total else 1.0,
        },
    )


def _summarize_retry_events(
    recent_events: list[dict[str, Any]], *, item_limit: int
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    failed = 0
    observable = 0
    for event in recent_events:
        event_type = str(event.get("event_type") or "")
        if event_type not in _RETRY_EVENTS:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        retry_payload = payload.get("retry")
        retry = retry_payload if isinstance(retry_payload, dict) else {}
        if event_type == "egress_failed":
            failed += 1
            if isinstance(retry.get("classification"), str):
                observable += 1
        error_payload = payload.get("error")
        error = error_payload if isinstance(error_payload, dict) else {}
        rows.append(
            {
                "timestamp": event.get("timestamp"),
                "trace_id": event.get("trace_id"),
                "channel": payload.get("channel"),
                "session_id": payload.get("session_id"),
                "event_type": event_type,
                "attempt": int(payload.get("attempt") or 0),
                "classification": retry.get("classification"),
                "should_retry": retry.get("should_retry"),
                "error_code": error.get("code"),
                "error_message": error.get("message"),
            }
        )
    rows = rows[-item_limit:]
    observability_rate = round((observable / failed), 4) if failed else 1.0
    return (
        rows,
        {
            "failed_count": failed,
            "observable_count": observable,
            "observability_rate": observability_rate,
        },
    )


def _summarize_sessions(
    session_bindings: list[SessionBinding], *, item_limit: int
) -> list[dict[str, object]]:
    rows = [
        {
            "session_id": binding.session_id,
            "thread_id": binding.thread_id,
            "ticket_id": binding.ticket_id,
            "updated_at": binding.updated_at.isoformat() if binding.updated_at else None,
            "channel": binding.metadata.get("channel"),
            "last_message_id": binding.metadata.get("last_message_id"),
            "replay_count": int(binding.metadata.get("replay_count", 0)),
        }
        for binding in session_bindings
    ]
    return rows[:item_limit]


def _as_int(raw: object) -> int:
    if isinstance(raw, int):
        return raw
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Show gateway status and recent traces")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    args = parser.parse_args()

    print(json.dumps(collect_status(args.env), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
