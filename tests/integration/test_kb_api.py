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


def test_kb_api_crud_flow(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "kb_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    build_runtime("dev")

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            before = _json(client, "GET", f"{base}/api/kb?source_type=faq&page=1&page_size=50")
            assert "items" in before
            assert isinstance(before["items"], list)

            created = _json(
                client,
                "POST",
                f"{base}/api/kb",
                {
                    "doc_id": "doc_kb_api_001",
                    "source_type": "faq",
                    "title": "门禁常见问题",
                    "content": "先检查授权，再重启门禁控制器。",
                    "tags": ["access", "faq"],
                },
            )
            assert created["data"]["doc_id"] == "doc_kb_api_001"
            assert created["data"]["source_type"] == "faq"

            listed = _json(
                client,
                "GET",
                f"{base}/api/kb?source_type=faq&q=门禁常见问题&page=1&page_size=50",
            )
            assert listed["total"] >= 1
            assert any(item["doc_id"] == "doc_kb_api_001" for item in listed["items"])

            updated = _json(
                client,
                "PATCH",
                f"{base}/api/kb/doc_kb_api_001",
                {
                    "title": "门禁FAQ更新版",
                    "content": "先核验权限并检查网络状态。",
                    "tags": ["access", "updated"],
                },
            )
            assert updated["data"]["doc_id"] == "doc_kb_api_001"
            assert updated["data"]["title"] == "门禁FAQ更新版"

            queried = _json(
                client,
                "GET",
                f"{base}/api/kb?source_type=faq&q=更新版&page=1&page_size=50",
            )
            assert queried["total"] >= 1
            assert any(item["doc_id"] == "doc_kb_api_001" for item in queried["items"])

            deleted = _json(client, "DELETE", f"{base}/api/kb/doc_kb_api_001")
            assert deleted["deleted"] is True
            assert deleted["doc_id"] == "doc_kb_api_001"

            after_delete = _json(
                client,
                "GET",
                f"{base}/api/kb?source_type=faq&q=门禁FAQ更新版&page=1&page_size=50",
            )
            assert all(item["doc_id"] != "doc_kb_api_001" for item in after_delete["items"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
