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


def test_ops_api_server_smoke(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ops_api_smoke.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-smoke-001",
        thread_id="thread-smoke-001",
        title="停车场道闸无法识别",
        latest_message="道闸今天一直不开",
        intent="repair",
        priority="P2",
        queue="support",
        metadata={"service_type": "parking", "community_name": "A区"},
    )
    runtime.trace_logger.log(
        "route_decision",
        {"intent": "repair", "channel": "wecom", "workflow": "support-intake"},
        trace_id="trace_ops_api_smoke_1",
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "handoff_decision",
        {"should_handoff": False, "reason": ""},
        trace_id="trace_ops_api_smoke_1",
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            health = _json(client, "GET", f"{base}/healthz")
            assert health["status"] == "ok"

            dashboard = _json(client, "GET", f"{base}/api/dashboard/summary")
            assert "data" in dashboard

            tickets = _json(client, "GET", f"{base}/api/tickets?page=1&page_size=20")
            assert tickets["total"] >= 1
            first_ticket_id = str(tickets["items"][0]["ticket_id"])

            detail = _json(client, "GET", f"{base}/api/tickets/{first_ticket_id}")
            assert detail["data"]["ticket_id"] == first_ticket_id

            _json(client, "GET", f"{base}/api/tickets/{first_ticket_id}/events")
            _json(client, "GET", f"{base}/api/tickets/{first_ticket_id}/assist")
            _json(client, "GET", f"{base}/api/tickets/{first_ticket_id}/similar-cases")

            claim = _json(
                client,
                "POST",
                f"{base}/api/tickets/{first_ticket_id}/claim",
                {"actor_id": "u_ops_01"},
            )
            assert claim["data"]["assignee"] == "u_ops_01"

            _json(
                client,
                "POST",
                f"{base}/api/tickets/{first_ticket_id}/resolve",
                {"actor_id": "u_ops_01", "resolution_note": "已远程恢复"},
            )
            close = _json(
                client,
                "POST",
                f"{base}/api/tickets/{first_ticket_id}/close",
                {"actor_id": "u_ops_01", "close_reason": "customer_confirmed"},
            )
            assert close["data"]["status"] == "closed"

            _json(client, "GET", f"{base}/api/queues")
            _json(client, "GET", f"{base}/api/queues/summary")

            traces = _json(client, "GET", f"{base}/api/traces?page=1&page_size=20")
            assert "items" in traces
            _json(client, "GET", f"{base}/api/traces/trace_ops_api_smoke_1")

            created = _json(
                client,
                "POST",
                f"{base}/api/kb",
                {
                    "doc_id": "doc_ops_smoke_001",
                    "source_type": "faq",
                    "title": "停车抬杆失败处理",
                    "content": "先核验车牌，再重置设备。",
                    "tags": ["parking", "gate"],
                },
            )
            assert created["data"]["doc_id"] == "doc_ops_smoke_001"
            _json(
                client,
                "PATCH",
                f"{base}/api/kb/doc_ops_smoke_001",
                {"title": "停车抬杆失败处理(更新)"},
            )
            deleted = _json(client, "DELETE", f"{base}/api/kb/doc_ops_smoke_001")
            assert deleted["deleted"] is True

            _json(client, "GET", f"{base}/api/channels/health")
            _json(client, "GET", f"{base}/api/channels/events")
            _json(client, "GET", f"{base}/api/openclaw/status")
            _json(client, "GET", f"{base}/api/openclaw/routes")
            assignees = _json(client, "GET", f"{base}/api/agents/assignees")
            assert "items" in assignees
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
