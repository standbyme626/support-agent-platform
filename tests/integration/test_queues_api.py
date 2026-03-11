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


def _get_json(client: httpx.Client, url: str) -> dict[str, Any]:
    response = client.get(url)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def test_queues_api_returns_queue_metrics(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "queues_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-queue-open",
        thread_id="thread-queue-open",
        title="门禁无法开门",
        latest_message="请尽快处理",
        intent="repair",
        priority="P2",
        queue="support",
        metadata={"service_type": "access"},
    )
    pending_ticket = runtime.ticket_api.create_ticket(
        channel="telegram",
        session_id="sess-queue-pending",
        thread_id="thread-queue-pending",
        title="停车位识别异常",
        latest_message="抬杆失败",
        intent="repair",
        priority="P1",
        queue="support",
        metadata={"service_type": "parking"},
    )
    runtime.ticket_api.assign_ticket(
        pending_ticket.ticket_id,
        assignee="u_ops_01",
        actor_id="u_ops_01",
    )
    escalated_ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-queue-escalated",
        thread_id="thread-queue-escalated",
        title="账单异常",
        latest_message="金额不一致",
        intent="billing",
        priority="P1",
        queue="billing",
        metadata={"service_type": "billing"},
    )
    runtime.ticket_api.assign_ticket(
        escalated_ticket.ticket_id,
        assignee="u_ops_02",
        actor_id="u_ops_02",
    )
    runtime.ticket_api.escalate_ticket(
        escalated_ticket.ticket_id,
        actor_id="u_ops_02",
        reason="billing risk",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            queues_payload = _get_json(client, f"{base}/api/queues")
            summary_payload = _get_json(client, f"{base}/api/queues/summary")

            assert "items" in queues_payload
            assert "items" in summary_payload
            assert isinstance(queues_payload["items"], list)
            assert isinstance(summary_payload["items"], list)
            assert queues_payload["items"] == summary_payload["items"]

            required_fields = {
                "queue_name",
                "open_count",
                "in_progress_count",
                "warning_count",
                "breached_count",
                "escalated_count",
                "assignee_count",
            }
            assert len(queues_payload["items"]) >= 2
            for row in queues_payload["items"]:
                assert required_fields.issubset(set(row.keys()))

            by_queue = {str(row["queue_name"]): row for row in queues_payload["items"]}
            assert by_queue["support"]["open_count"] >= 1
            assert by_queue["support"]["in_progress_count"] >= 1
            assert by_queue["support"]["assignee_count"] >= 1
            assert by_queue["billing"]["escalated_count"] >= 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
