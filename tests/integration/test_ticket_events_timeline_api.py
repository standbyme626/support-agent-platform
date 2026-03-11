from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
from pytest import MonkeyPatch

from scripts.ops_api_server import _build_handler, build_runtime


def _start_server(environment: str) -> tuple[ThreadingHTTPServer, threading.Thread]:
    runtime = build_runtime(environment)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _build_handler(runtime))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _json(
    client: httpx.Client, method: str, url: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = client.request(method, url, json=payload)
    response.raise_for_status()
    data = response.json()
    assert isinstance(data, dict)
    return data


def test_ticket_events_timeline_contains_trace_observability_events(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_events_timeline_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-ticket-timeline-001",
        thread_id="thread-ticket-timeline-001",
        title="门禁异常",
        latest_message="门禁刷卡失败",
        intent="repair",
        priority="P2",
        queue="support",
        metadata={"community_name": "A区", "service_type": "access_control"},
    )

    trace_id = "trace_ticket_timeline_api_1"
    runtime.trace_logger.log(
        "ingress_normalized",
        {
            "channel": "wecom",
            "inbox": "wecom",
            "session_id": ticket.session_id,
            "idempotency_key": "msg-1",
        },
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "route_decision",
        {
            "intent": "repair",
            "confidence": 0.91,
            "is_low_confidence": False,
            "reason": "keyword_match",
        },
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "sla_evaluated",
        {
            "matched_rule_id": "rule-repair-p2",
            "matched_rule_path": "sla.repair.p2",
            "used_fallback": False,
        },
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "handoff_decision",
        {"should_handoff": False, "reason": "no_handoff", "policy_version": "handoff_policy_v1"},
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    required_event_types = {
        "ingress_normalized",
        "route_decision",
        "sla_evaluated",
        "handoff_decision",
    }

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            events = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/events")
            assert "items" in events
            items = events["items"]
            assert isinstance(items, list)
            assert items

            event_types = {str(item.get("event_type")) for item in items if isinstance(item, dict)}
            assert required_event_types.issubset(event_types)

            trace_items = [
                item
                for item in items
                if isinstance(item, dict) and item.get("event_type") in required_event_types
            ]
            assert trace_items
            for item in trace_items:
                assert item.get("ticket_id") == ticket.ticket_id
                assert item.get("source") == "trace"
                assert item.get("trace_id") == trace_id
                assert item.get("created_at")
                payload = item.get("payload")
                assert isinstance(payload, dict)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
