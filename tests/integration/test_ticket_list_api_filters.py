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


def test_ticket_list_filters_pagination_and_sort(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_list_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")

    ticket_a = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-ticket-list-a",
        thread_id="thread-ticket-list-a",
        title="停车杆故障",
        latest_message="车辆无法抬杆",
        intent="repair",
        priority="P2",
        queue="support",
        metadata={"service_type": "parking"},
    )
    ticket_b = runtime.ticket_api.create_ticket(
        channel="telegram",
        session_id="sess-ticket-list-b",
        thread_id="thread-ticket-list-b",
        title="账单争议",
        latest_message="账单扣费异常",
        intent="billing",
        priority="P1",
        queue="billing",
        metadata={"service_type": "billing"},
    )
    runtime.ticket_api.assign_ticket(
        ticket_b.ticket_id,
        assignee="u_ops_02",
        actor_id="u_ops_02",
    )
    runtime.ticket_api.escalate_ticket(
        ticket_b.ticket_id,
        actor_id="u_ops_02",
        reason="billing risk",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            status_filtered = client.get(
                f"{base}/api/tickets?status=escalated&page=1&page_size=10"
            )
            assert status_filtered.status_code == 200
            status_payload = status_filtered.json()
            assert status_payload["total"] >= 1
            assert all(item["status"] == "escalated" for item in status_payload["items"])

            service_filtered = client.get(
                f"{base}/api/tickets?service_type=parking&page=1&page_size=10"
            )
            assert service_filtered.status_code == 200
            service_payload = service_filtered.json()
            assert service_payload["total"] >= 1
            assert any(item["ticket_id"] == ticket_a.ticket_id for item in service_payload["items"])

            page_1 = client.get(
                f"{base}/api/tickets?page=1&page_size=1&sort_by=priority&sort_order=asc"
            )
            page_2 = client.get(
                f"{base}/api/tickets?page=2&page_size=1&sort_by=priority&sort_order=asc"
            )
            assert page_1.status_code == 200
            assert page_2.status_code == 200
            payload_1 = page_1.json()
            payload_2 = page_2.json()
            assert payload_1["page"] == 1
            assert payload_1["page_size"] == 1
            assert payload_1["total"] >= 2
            assert payload_2["page"] == 2

            first_priority = payload_1["items"][0]["priority"]
            second_priority = payload_2["items"][0]["priority"]
            assert first_priority <= second_priority
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
