from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config
from core.trace_logger import JsonTraceLogger

DEFAULT_REQUIRED_EVENTS = (
    "ingress_normalized",
    "egress_rendered",
    "route_decision",
    "sla_evaluated",
    "recommended_actions",
    "handoff_decision",
)


def group_trace_events(
    events: list[dict[str, object]],
    *,
    trace_ids: set[str] | None = None,
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for event in events:
        trace_id = event.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id.strip():
            continue
        if trace_ids is not None and trace_id not in trace_ids:
            continue
        grouped.setdefault(trace_id, []).append(event)
    return grouped


def compute_trace_kpi(
    grouped_events: dict[str, list[dict[str, object]]],
    *,
    required_events: tuple[str, ...] = DEFAULT_REQUIRED_EVENTS,
) -> dict[str, object]:
    trace_count = len(grouped_events)
    required_count = len(required_events)
    complete_count = 0
    missing_total = 0
    traces: list[dict[str, object]] = []

    for trace_id, events in grouped_events.items():
        event_types = {
            str(item.get("event_type", ""))
            for item in events
            if isinstance(item.get("event_type"), str)
        }
        missing = [event for event in required_events if event not in event_types]
        if not missing:
            complete_count += 1
        missing_total += len(missing)
        traces.append(
            {
                "trace_id": trace_id,
                "event_count": len(events),
                "complete": not missing,
                "missing_events": missing,
            }
        )

    chain_complete_rate = complete_count / trace_count if trace_count else 0.0
    denominator = trace_count * required_count if trace_count and required_count else 1
    critical_missing_rate = missing_total / denominator
    traces.sort(key=lambda item: str(item["trace_id"]))

    return {
        "required_events": list(required_events),
        "trace_count": trace_count,
        "complete_trace_count": complete_count,
        "chain_complete_rate": round(chain_complete_rate, 4),
        "critical_missing_rate": round(critical_missing_rate, 4),
        "missing_event_total": missing_total,
        "traces": traces,
    }


def generate_trace_kpi(
    *,
    environment: str | None,
    log_path: Path | None,
    trace_ids: set[str] | None = None,
    required_events: tuple[str, ...] = DEFAULT_REQUIRED_EVENTS,
) -> dict[str, object]:
    resolved_log_path = log_path
    if resolved_log_path is None:
        app_config = load_app_config(environment)
        resolved_log_path = Path(app_config.gateway.log_path)

    logger = JsonTraceLogger(resolved_log_path)
    recent_events = logger.read_recent(limit=200000)
    grouped = group_trace_events(recent_events, trace_ids=trace_ids)
    report = compute_trace_kpi(grouped, required_events=required_events)
    report["log_path"] = str(resolved_log_path)
    return report


def _parse_csv(value: str | None) -> set[str] | None:
    if value is None:
        return None
    items = {part.strip() for part in value.split(",") if part.strip()}
    return items or None


def _parse_required_events(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_REQUIRED_EVENTS
    events = [part.strip() for part in value.split(",") if part.strip()]
    return tuple(events) if events else DEFAULT_REQUIRED_EVENTS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute trace KPI metrics from gateway/workflow log"
    )
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--log-path", default=None, help="Override trace log path")
    parser.add_argument("--trace-ids", default=None, help="Comma-separated trace IDs")
    parser.add_argument(
        "--required-events",
        default=None,
        help="Comma-separated required events for completeness check",
    )
    parser.add_argument("--output", default=None, help="Optional output json path")
    args = parser.parse_args()

    report = generate_trace_kpi(
        environment=args.env,
        log_path=Path(args.log_path) if args.log_path else None,
        trace_ids=_parse_csv(args.trace_ids),
        required_events=_parse_required_events(args.required_events),
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
