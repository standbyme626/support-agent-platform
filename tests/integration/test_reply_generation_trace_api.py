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


def test_trace_detail_exposes_reply_generation_metadata(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "reply_trace_api.db"))
    monkeypatch.setenv("SUPPORT_AGENT_GATEWAY_LOG_PATH", str(tmp_path / "reply_trace_api.log"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-reply-trace",
        thread_id="thread-reply-trace",
        title="进度查询",
        latest_message="我的工单到哪了",
        intent="progress_query",
        priority="P3",
        queue="support",
    )
    trace_id = "trace_reply_meta_001"
    runtime.trace_logger.log(
        "route_decision",
        {"intent": "progress_query", "confidence": 0.91, "workflow": "support-intake"},
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )
    runtime.trace_logger.log(
        "reply_generated",
        {
            "provider": "fallback",
            "model": None,
            "prompt_key": "progress_reply",
            "prompt_version": "v1",
            "success": False,
            "fallback_used": True,
            "degraded": True,
            "degrade_reason": "schema_parse_error",
            "generation_type": "progress",
            "grounding_sources": ["history_case:doc-001"],
        },
        trace_id=trace_id,
        ticket_id=ticket.ticket_id,
        session_id=ticket.session_id,
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.get(f"{base}/api/traces/{trace_id}")
            response.raise_for_status()
            data = response.json()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert data["trace_id"] == trace_id
    assert data["prompt_key"] == "progress_reply"
    assert data["prompt_version"] == "v1"
    assert data["fallback_used"] is True
    assert data["degraded"] is True
    assert data["degrade_reason"] == "schema_parse_error"
    assert data["generation_type"] == "progress"
