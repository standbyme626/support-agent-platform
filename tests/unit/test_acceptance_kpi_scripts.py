from __future__ import annotations

from scripts.run_acceptance import _build_replay_command, _to_markdown
from scripts.trace_kpi import compute_trace_kpi, group_trace_events


def test_trace_kpi_computes_chain_and_missing_rates() -> None:
    events = [
        {"trace_id": "trace-a", "event_type": "ingress_normalized"},
        {"trace_id": "trace-a", "event_type": "egress_rendered"},
        {"trace_id": "trace-a", "event_type": "route_decision"},
        {"trace_id": "trace-a", "event_type": "sla_evaluated"},
        {"trace_id": "trace-a", "event_type": "recommended_actions"},
        {"trace_id": "trace-a", "event_type": "handoff_decision"},
        {"trace_id": "trace-b", "event_type": "ingress_normalized"},
        {"trace_id": "trace-b", "event_type": "egress_rendered"},
    ]
    grouped = group_trace_events(events)
    report = compute_trace_kpi(grouped)

    assert report["trace_count"] == 2
    assert report["complete_trace_count"] == 1
    assert report["chain_complete_rate"] == 0.5
    assert report["critical_missing_rate"] > 0.0


def test_markdown_includes_failure_replay_command() -> None:
    summary = {
        "generated_at": "2026-03-11T00:00:00+00:00",
        "total": 1,
        "passed": 0,
        "failed": 1,
        "results": [
            {
                "id": "sample-x",
                "trace_id": "trace-x",
                "passed": False,
                "failures": ["missing required events"],
                "replay_command": _build_replay_command(
                    channel="telegram",
                    session_id="demo-1",
                    text="hello",
                    trace_id="trace-x",
                ),
            }
        ],
    }
    kpi = {
        "chain_complete_rate": 0.0,
        "critical_missing_rate": 0.5,
    }

    markdown = _to_markdown(summary, kpi)
    assert "reproduce:" in markdown
    assert "trace-x" in markdown
