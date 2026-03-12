from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
from pytest import MonkeyPatch

from scripts.ops_api_server import _build_handler, build_runtime


def _start_server(environment: str) -> tuple[ThreadingHTTPServer, threading.Thread]:
    runtime = build_runtime(environment)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _build_handler(runtime))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_dashboard_api_summary_and_recent_errors(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "dashboard_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-dashboard-001",
        thread_id="thread-dashboard-001",
        title="电梯停运",
        latest_message="1号楼电梯停了",
        intent="repair",
        priority="P1",
        queue="support",
    )

    runtime.trace_logger.log(
        "route_failed",
        {"error": "route_timeout", "channel": "wecom"},
        trace_id="trace_dashboard_001",
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "consulting_ticket_reused",
        {"ticket_id": ticket.ticket_id, "intent": "faq"},
        trace_id="trace_dashboard_002",
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "duplicate_candidates_generated",
        {"ticket_id": ticket.ticket_id, "candidate_count": 1},
        trace_id="trace_dashboard_003",
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "merge_suggestion_accepted",
        {"source_ticket_id": ticket.ticket_id, "target_ticket_id": "TCK-TARGET"},
        trace_id="trace_dashboard_004",
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "merge_suggestion_rejected",
        {"source_ticket_id": ticket.ticket_id, "target_ticket_id": "TCK-TARGET"},
        trace_id="trace_dashboard_005",
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            summary = client.get(f"{base}/api/dashboard/summary")
            assert summary.status_code == 200
            summary_payload = summary.json()
            assert "request_id" in summary_payload
            assert "data" in summary_payload
            assert "new_tickets_today" in summary_payload["data"]
            assert "consulting_reuse_count" in summary_payload["data"]
            assert "duplicate_candidates_count" in summary_payload["data"]
            assert "merge_accept_count" in summary_payload["data"]
            assert "merge_reject_count" in summary_payload["data"]
            assert "merge_accept_rate" in summary_payload["data"]
            assert summary_payload["data"]["consulting_reuse_count"] >= 1
            assert summary_payload["data"]["duplicate_candidates_count"] >= 1
            assert summary_payload["data"]["merge_accept_count"] >= 1
            assert summary_payload["data"]["merge_reject_count"] >= 1

            recent_errors = client.get(f"{base}/api/dashboard/recent-errors")
            assert recent_errors.status_code == 200
            recent_payload = recent_errors.json()
            assert "request_id" in recent_payload
            assert isinstance(recent_payload["data"], list)
            assert any(
                item.get("trace_id") == "trace_dashboard_001"
                for item in recent_payload["data"]
            )

            not_found = client.get(f"{base}/api/dashboard/not-exists")
            assert not_found.status_code == 404
            not_found_payload = not_found.json()
            assert "code" in not_found_payload
            assert "message" in not_found_payload
            assert "request_id" in not_found_payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
