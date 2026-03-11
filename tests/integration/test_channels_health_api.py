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


def test_channels_health_and_events_api(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "channels_health_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    runtime.gateway.receive(
        "telegram",
        {
            "update_id": 201,
            "message": {
                "chat": {"id": 2026, "username": "integration"},
                "text": "gateway health check",
            },
        },
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            health_payload = _get_json(client, f"{base}/api/channels/health")
            events_payload = _get_json(client, f"{base}/api/channels/events")

            assert isinstance(health_payload.get("items"), list)
            assert isinstance(events_payload.get("items"), list)

            health_items = health_payload["items"]
            assert len(health_items) >= 1
            required_health_fields = {
                "channel",
                "connected",
                "last_event_at",
                "last_error",
                "retry_state",
            }
            for row in health_items:
                assert required_health_fields.issubset(set(row.keys()))
            assert any(str(row.get("channel")) == "telegram" for row in health_items)

            events_items = events_payload["items"]
            assert len(events_items) >= 1
            required_event_fields = {"timestamp", "trace_id", "channel", "event_type", "payload"}
            for row in events_items:
                assert required_event_fields.issubset(set(row.keys()))
                assert isinstance(row["payload"], dict)
            assert any(str(row.get("channel")) == "telegram" for row in events_items)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
