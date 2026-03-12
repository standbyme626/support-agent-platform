from __future__ import annotations

import threading
from http import HTTPStatus
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


def test_copilot_endpoints_success_paths(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "copilot_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-copilot-001",
        thread_id="thread-copilot-001",
        title="门禁告警误触发",
        latest_message="门禁夜间频繁报警",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            operator = _json(
                client,
                "POST",
                f"{base}/api/copilot/operator/query",
                {"query": "请给我今日处理优先级建议"},
            )
            assert operator["data"]["scope"] == "operator"
            assert operator["data"]["answer"]
            assert isinstance(operator["data"]["grounding_sources"], list)
            assert isinstance(operator["data"]["llm_trace"], dict)

            queue = _json(
                client,
                "POST",
                f"{base}/api/copilot/queue/query",
                {"query": "support队列需要优先做什么", "queue": "support"},
            )
            assert queue["data"]["scope"] == "queue"
            assert queue["data"]["answer"]
            assert isinstance(queue["data"]["queue_summary"], list)

            ticket_query = _json(
                client,
                "POST",
                f"{base}/api/copilot/ticket/{ticket.ticket_id}/query",
                {"query": "这张单下一步怎么推进"},
            )
            assert ticket_query["data"]["scope"] == "ticket"
            assert ticket_query["data"]["ticket_id"] == ticket.ticket_id
            assert ticket_query["data"]["summary"]
            assert isinstance(ticket_query["data"]["grounding_sources"], list)
            assert isinstance(ticket_query["data"]["llm_trace"], dict)

            dispatch = _json(
                client,
                "POST",
                f"{base}/api/copilot/dispatch/query",
                {"query": "请给出调度建议"},
            )
            assert dispatch["data"]["scope"] == "dispatch"
            assert dispatch["data"]["answer"]
            assert isinstance(dispatch["data"]["dispatch_priority"], list)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_copilot_endpoint_rejects_missing_query(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "copilot_api_invalid.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.post(f"{base}/api/copilot/operator/query", json={})
            assert response.status_code == HTTPStatus.BAD_REQUEST
            payload = response.json()
            assert payload["code"] == "invalid_payload"
            assert payload["message"] == "query is required"
            assert payload["request_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
