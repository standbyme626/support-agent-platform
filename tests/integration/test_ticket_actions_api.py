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


def test_ticket_actions_chain_and_timeline(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_actions_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-ticket-actions-001",
        thread_id="thread-ticket-actions-001",
        title="门禁故障",
        latest_message="刷卡没反应",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            detail = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}")
            assert detail["data"]["status"] == "open"

            claimed = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/claim",
                {"actor_id": "u_ops_01"},
            )
            assert claimed["data"]["status"] == "pending"
            assert claimed["data"]["assignee"] == "u_ops_01"

            reassigned = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/reassign",
                {
                    "actor_id": "u_ops_01",
                    "target_queue": "billing",
                    "target_assignee": "u_ops_02",
                },
            )
            assert reassigned["data"]["queue"] == "billing"
            assert reassigned["data"]["assignee"] == "u_ops_02"

            escalated = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/escalate",
                {"actor_id": "u_ops_02", "note": "need supervisor"},
            )
            assert escalated["data"]["status"] == "pending"
            assert escalated["data"]["handoff_state"] == "pending_approval"
            approval_id = str(escalated["data"]["approval_id"])
            assert approval_id

            pending = _json(client, "GET", f"{base}/api/approvals/pending?page=1&page_size=20")
            pending_ids = {item["approval_id"] for item in pending["items"]}
            assert approval_id in pending_ids

            approved = _json(
                client,
                "POST",
                f"{base}/api/approvals/{approval_id}/approve",
                {"actor_id": "u_supervisor_01", "note": "approved"},
            )
            assert approved["data"]["status"] == "escalated"

            resolved = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/resolve",
                {
                    "actor_id": "u_ops_02",
                    "resolution_note": "已远程重启",
                    "resolution_code": "remote_reboot",
                },
            )
            assert resolved["data"]["status"] == "resolved"

            closed = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/close",
                {
                    "actor_id": "u_ops_02",
                    "resolution_note": "客户确认恢复",
                    "close_reason": "customer_confirmed",
                },
            )
            assert closed["data"]["status"] == "closed"

            events = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/events")
            event_types = {item["event_type"] for item in events["items"]}
            assert "ticket_assigned" in event_types
            assert "ticket_reassign_requested" in event_types
            assert "approval_requested" in event_types
            assert "approval_decision" in event_types
            assert "ticket_resolved" in event_types
            assert "ticket_closed" in event_types

            for item in events["items"]:
                assert item["actor_id"]
                assert item["created_at"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_approval_reject_and_timeout_paths(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_approval_reject_timeout.db")
    )
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-ticket-approval-002",
        thread_id="thread-ticket-approval-002",
        title="停车场道闸故障",
        latest_message="道闸无法抬杆",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            first_request = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/escalate",
                {"actor_id": "u_ops_01", "note": "need supervisor"},
            )
            approval_id = str(first_request["data"]["approval_id"])
            assert approval_id

            rejected = _json(
                client,
                "POST",
                f"{base}/api/approvals/{approval_id}/reject",
                {"actor_id": "u_supervisor_01", "note": "insufficient context"},
            )
            assert rejected["approval"]["status"] == "rejected"

            timeout_request = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/escalate",
                {"actor_id": "u_ops_01", "note": "need supervisor", "timeout_minutes": 0},
            )
            assert timeout_request["data"]["status"] == "open"
            assert timeout_request["data"]["handoff_state"] == "pending_approval"

            pending = _json(client, "GET", f"{base}/api/approvals/pending?page=1&page_size=20")
            assert pending["items"] == []

            actions = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/pending-actions")
            statuses = {item["status"] for item in actions["items"]}
            assert {"rejected", "timeout"}.issubset(statuses)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
