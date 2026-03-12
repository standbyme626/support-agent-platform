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


def test_reply_events_api_supports_session_and_ticket_views(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "reply_events_api.db"))
    monkeypatch.setenv("SUPPORT_AGENT_GATEWAY_LOG_PATH", str(tmp_path / "reply_events_api.log"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    first_ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-reply-events-001",
        thread_id="thread-reply-events-001",
        title="停车场抬杆异常",
        latest_message="抬杆失败",
        intent="repair",
        priority="P2",
        queue="support",
    )
    second_ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-reply-events-001",
        thread_id="thread-reply-events-001",
        title="电梯异响",
        latest_message="电梯有异响",
        intent="repair",
        priority="P2",
        queue="support",
    )

    runtime.trace_logger.log(
        "reply_generated",
        {
            "provider": "fallback",
            "model": None,
            "prompt_key": "disambiguation_reply",
            "prompt_version": "v1",
            "success": False,
            "fallback_used": True,
            "degraded": True,
            "degrade_reason": "llm_provider_error",
            "generation_type": "disambiguation",
            "tone": "professional_warm",
            "workflow": "support-intake",
            "grounding_sources": ["history_case:doc-001"],
            "reply_preview": "请确认你在跟进哪一个问题",
        },
        trace_id="trace_reply_events_disambiguation_001",
        ticket_id=second_ticket.ticket_id,
        session_id=second_ticket.session_id,
    )
    runtime.trace_logger.log(
        "route_decision",
        {"intent": "repair", "confidence": 0.81},
        trace_id="trace_reply_events_non_reply_001",
        ticket_id=second_ticket.ticket_id,
        session_id=second_ticket.session_id,
    )
    runtime.trace_logger.log(
        "reply_generated",
        {
            "provider": "fallback",
            "model": None,
            "prompt_key": "switch_reply",
            "prompt_version": "v1",
            "success": False,
            "fallback_used": True,
            "degraded": True,
            "degrade_reason": "schema_parse_error",
            "generation_type": "switch",
            "tone": "professional_warm",
            "workflow": "support-intake",
            "grounding_sources": ["history_case:doc-002"],
            "reply_preview": "已切换到你指定的工单继续跟进",
        },
        trace_id="trace_reply_events_switch_001",
        ticket_id=first_ticket.ticket_id,
        session_id=first_ticket.session_id,
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            session_events = _json(
                client,
                "GET",
                f"{base}/api/sessions/{first_ticket.session_id}/reply-events",
            )
            session_items = session_events["items"]
            assert len(session_items) == 2
            assert {item["generation_type"] for item in session_items} == {
                "disambiguation",
                "switch",
            }
            assert all(item["event_type"] == "reply_generated" for item in session_items)
            assert all(item["source"] == "trace" for item in session_items)
            assert all(item["session_id"] == first_ticket.session_id for item in session_items)

            disambiguation_item = next(
                item for item in session_items if item["generation_type"] == "disambiguation"
            )
            assert disambiguation_item["prompt_key"] == "disambiguation_reply"
            assert disambiguation_item["fallback_used"] is True
            assert disambiguation_item["degrade_reason"] == "llm_provider_error"

            switch_item = next(
                item for item in session_items if item["generation_type"] == "switch"
            )
            assert switch_item["prompt_key"] == "switch_reply"
            assert switch_item["fallback_used"] is True
            assert switch_item["degrade_reason"] == "schema_parse_error"

            first_ticket_events = _json(
                client,
                "GET",
                f"{base}/api/tickets/{first_ticket.ticket_id}/reply-events",
            )
            assert len(first_ticket_events["items"]) == 1
            assert first_ticket_events["items"][0]["generation_type"] == "switch"
            assert first_ticket_events["items"][0]["prompt_key"] == "switch_reply"

            second_ticket_events = _json(
                client,
                "GET",
                f"{base}/api/tickets/{second_ticket.ticket_id}/reply-events",
            )
            assert len(second_ticket_events["items"]) == 1
            assert second_ticket_events["items"][0]["generation_type"] == "disambiguation"
            assert second_ticket_events["items"][0]["prompt_key"] == "disambiguation_reply"

            missing_ticket = client.get(f"{base}/api/tickets/TCK-UNKNOWN/reply-events")
            assert missing_ticket.status_code == HTTPStatus.NOT_FOUND

            missing_session = client.get(f"{base}/api/sessions/sess-unknown/reply-events")
            assert missing_session.status_code == HTTPStatus.NOT_FOUND
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
