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


def test_openclaw_status_and_routes_api(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "openclaw_routes_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            status_payload = _get_json(client, f"{base}/api/openclaw/status")
            routes_payload = _get_json(client, f"{base}/api/openclaw/routes")
            retries_payload = _get_json(client, f"{base}/api/openclaw/retries")
            replays_payload = _get_json(client, f"{base}/api/openclaw/replays")
            sessions_payload = _get_json(client, f"{base}/api/openclaw/sessions")

            assert "data" in status_payload
            assert isinstance(status_payload["data"], dict)
            status_data = status_payload["data"]
            assert status_data["environment"] == "dev"
            assert isinstance(status_data["gateway"], str)
            assert isinstance(status_data["session_bindings"], int)

            assert isinstance(routes_payload.get("routes"), list)
            routes = routes_payload["routes"]
            assert len(routes) >= 1
            assert routes_payload["gateway"] == status_data["gateway"]
            for route in routes:
                assert {"channel", "mode"}.issubset(set(route.keys()))
                assert route["mode"] == "ingress/session/routing"

            assert isinstance(retries_payload.get("items"), list)
            assert {"page", "page_size", "total", "observability_rate"}.issubset(
                set(retries_payload.keys())
            )
            assert isinstance(replays_payload.get("items"), list)
            assert {"page", "page_size", "total", "duplicate_count", "duplicate_ratio"}.issubset(
                set(replays_payload.keys())
            )
            assert isinstance(sessions_payload.get("items"), list)
            assert {"page", "page_size", "total", "bound_to_ticket"}.issubset(
                set(sessions_payload.keys())
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
