from __future__ import annotations

import threading
import uuid
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


def test_traces_api_list_filters_and_detail(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "traces_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket_a = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-traces-a",
        thread_id="thread-traces-a",
        title="电梯停运",
        latest_message="电梯无法启动",
        intent="repair",
        priority="P1",
        queue="support",
    )
    ticket_b = runtime.ticket_api.create_ticket(
        channel="telegram",
        session_id="sess-traces-b",
        thread_id="thread-traces-b",
        title="账单问题",
        latest_message="账单扣费有误",
        intent="billing",
        priority="P2",
        queue="billing",
    )

    trace_a = f"trace_api_{uuid.uuid4().hex[:10]}"
    runtime.trace_logger.log(
        "ingress_normalized",
        {"channel": "wecom", "inbox": "wecom", "session_id": ticket_a.session_id},
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "route_decision",
        {
            "intent": "repair",
            "confidence": 0.92,
            "workflow": "support-intake",
            "channel": "wecom",
            "provider": "openai-compatible",
        },
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "ticket_context_retrieved",
        {
            "doc_ids": ["doc-elevator-1", "doc-elevator-2"],
            "grounding_sources": [
                {
                    "source_type": "history_case",
                    "source_id": "doc-elevator-1",
                    "title": "电梯停运应急案例",
                    "snippet": "先断电复位并通知值班工程师",
                    "score": 0.91,
                    "rank": 1,
                    "reason": "rerank:title_match",
                    "retrieval_mode": "hybrid",
                }
            ],
        },
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "tool_call",
        {"tool": "search_kb"},
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "recommended_actions",
        {"actions": [{"action": "dispatch_engineer"}]},
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "summary_generated",
        {
            "provider": "openai-compatible",
            "model": "qwen3.5:9b",
            "prompt_key": "case_summary",
            "prompt_version": "v2",
            "latency_ms": 86,
            "request_id": "req-trace-a",
            "token_usage": {"prompt_tokens": 22, "completion_tokens": 11, "total_tokens": 33},
            "retry_count": 1,
            "success": True,
            "error": None,
            "fallback_used": False,
            "degraded": False,
        },
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "handoff_decision",
        {"should_handoff": True, "reason": "high_risk"},
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "approval_requested",
        {
            "approval_id": "apr_trace_a_001",
            "action": "ticket_escalate",
            "actor_id": "u_ops_01",
            "timeout_at": "2026-03-12T10:00:00+00:00",
        },
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )
    runtime.trace_logger.log(
        "approval_decision",
        {
            "approval_id": "apr_trace_a_001",
            "status": "approved",
            "actor_id": "u_supervisor_01",
            "decided_at": "2026-03-12T10:01:00+00:00",
        },
        trace_id=trace_a,
        ticket_id=ticket_a.ticket_id,
        session_id=ticket_a.session_id,
    )

    trace_b = f"trace_api_{uuid.uuid4().hex[:10]}"
    runtime.trace_logger.log(
        "route_decision",
        {
            "intent": "billing",
            "confidence": 0.81,
            "workflow": "support-intake",
            "channel": "telegram",
            "provider": "openai-compatible",
        },
        trace_id=trace_b,
        ticket_id=ticket_b.ticket_id,
        session_id=ticket_b.session_id,
    )
    runtime.trace_logger.log(
        "handoff_decision",
        {"should_handoff": False, "reason": ""},
        trace_id=trace_b,
        ticket_id=ticket_b.ticket_id,
        session_id=ticket_b.session_id,
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            traces = _json(client, "GET", f"{base}/api/traces?page=1&page_size=20")
            assert traces["total"] >= 2
            by_trace_a = _json(
                client,
                "GET",
                f"{base}/api/traces?trace_id={trace_a}&page=1&page_size=20",
            )
            assert by_trace_a["total"] >= 1
            assert any(item["trace_id"] == trace_a for item in by_trace_a["items"])

            by_trace_b = _json(
                client,
                "GET",
                f"{base}/api/traces?trace_id={trace_b}&page=1&page_size=20",
            )
            assert by_trace_b["total"] >= 1
            assert any(item["trace_id"] == trace_b for item in by_trace_b["items"])

            by_channel = _json(
                client,
                "GET",
                f"{base}/api/traces?channel=wecom&page=1&page_size=20",
            )
            assert by_channel["total"] >= 1
            assert all(item["channel"] == "wecom" for item in by_channel["items"])

            by_handoff = _json(
                client,
                "GET",
                f"{base}/api/traces?handoff=true&trace_id={trace_a}&page=1&page_size=20",
            )
            assert any(item["trace_id"] == trace_a for item in by_handoff["items"])

            by_prompt_version = _json(
                client,
                "GET",
                f"{base}/api/traces?prompt_version=v2&page=1&page_size=20",
            )
            assert any(item["trace_id"] == trace_a for item in by_prompt_version["items"])

            by_ticket = _json(
                client,
                "GET",
                f"{base}/api/traces?ticket_id={ticket_a.ticket_id}&page=1&page_size=20",
            )
            assert by_ticket["total"] >= 1
            assert all(item["ticket_id"] == ticket_a.ticket_id for item in by_ticket["items"])

            by_session = _json(
                client,
                "GET",
                f"{base}/api/traces?session_id={ticket_a.session_id}&page=1&page_size=20",
            )
            assert by_session["total"] >= 1
            assert all(item["session_id"] == ticket_a.session_id for item in by_session["items"])

            detail = _json(client, "GET", f"{base}/api/traces/{trace_a}")
            assert detail["trace_id"] == trace_a
            assert detail["ticket_id"] == ticket_a.ticket_id
            assert detail["session_id"] == ticket_a.session_id
            assert detail["route_decision"]["intent"] == "repair"
            assert "search_kb" in detail["tool_calls"]
            assert "doc-elevator-1" in detail["retrieved_docs"]
            assert detail["grounding_sources"][0]["source_id"] == "doc-elevator-1"
            assert detail["handoff"] is True
            assert detail["model"] == "qwen3.5:9b"
            assert detail["prompt_key"] == "case_summary"
            assert detail["prompt_version"] == "v2"
            assert detail["retry_count"] == 1
            assert detail["success"] is True
            assert detail["error"] is None
            assert detail["degraded"] is False
            assert isinstance(detail["events"], list)
            event_types = {item["event_type"] for item in detail["events"]}
            assert "route_decision" in event_types
            assert "handoff_decision" in event_types
            assert "summary_generated" in event_types
            assert "approval_requested" in event_types
            assert "approval_decision" in event_types
            approval_requested_event = next(
                item for item in detail["events"] if item["event_type"] == "approval_requested"
            )
            assert approval_requested_event["payload"]["approval_id"] == "apr_trace_a_001"
            assert approval_requested_event["payload"]["actor_id"] == "u_ops_01"
            approval_decision_event = next(
                item for item in detail["events"] if item["event_type"] == "approval_decision"
            )
            assert approval_decision_event["payload"]["status"] == "approved"
            assert approval_decision_event["payload"]["actor_id"] == "u_supervisor_01"
            assert approval_decision_event["payload"]["decided_at"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
