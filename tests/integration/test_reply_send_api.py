from __future__ import annotations

import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
from pytest import MonkeyPatch

from channel_adapters.base import ChannelAdapterError
from scripts.ops_api_server import _build_handler, build_runtime


def _start_server(runtime: Any) -> tuple[ThreadingHTTPServer, threading.Thread]:
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


def test_reply_send_and_reply_draft_support_manual_loop(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "reply_send_api_success.db"))
    monkeypatch.setenv("SUPPORT_AGENT_GATEWAY_LOG_PATH", str(tmp_path / "reply_send_api_success.log"))
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv("WECOM_APP_API_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-reply-send-001",
        thread_id="thread-reply-send-001",
        title="电梯门异常开合",
        latest_message="电梯门持续开合无法稳定",
        intent="repair",
        priority="P2",
        queue="support",
        customer_id="wx_user_001",
        metadata={"sender_id": "wx_user_001"},
    )

    server, thread = _start_server(runtime)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            draft = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{ticket.ticket_id}/reply-draft",
                {
                    "actor_id": "u_ops_01",
                    "actor_role": "operator",
                    "style": "说明",
                    "max_length": 180,
                    "trace_id": "trace_reply_draft_001",
                },
            )
            assert draft["data"]["advice_only"] is True
            assert isinstance(draft["data"]["draft_text"], str)
            assert draft["data"]["trace_id"] == "trace_reply_draft_001"

            send_trace_id = "trace_reply_send_success_001"
            first_send = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{ticket.ticket_id}/reply-send",
                {
                    "actor_id": "u_ops_01",
                    "actor_role": "operator",
                    "content": "您好，我们已安排工程师处理，预计 30 分钟内恢复。",
                    "idempotency_key": "idem-reply-send-001",
                    "trace_id": send_trace_id,
                },
            )
            assert first_send["data"]["dedup_hit"] is False
            assert first_send["data"]["attempt"] == 1
            assert first_send["data"]["delivery_status"] in {"queued", "sent"}
            assert first_send["data"]["target"]["to_user_id"] == "wx_user_001"

            second_send = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{ticket.ticket_id}/reply-send",
                {
                    "actor_id": "u_ops_01",
                    "actor_role": "operator",
                    "content": "您好，我们已安排工程师处理，预计 30 分钟内恢复。",
                    "idempotency_key": "idem-reply-send-001",
                    "trace_id": "trace_reply_send_success_002",
                },
            )
            assert second_send["data"]["dedup_hit"] is True
            assert second_send["data"]["attempt"] == 1
            assert second_send["data"]["delivery_status"] == first_send["data"]["delivery_status"]

            reply_events = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/reply-events")
            event_types = [str(item.get("event_type")) for item in reply_events["items"]]
            assert "reply_draft_generated" in event_types
            assert "reply_send_requested" in event_types
            assert "reply_send_delivered" in event_types
            assert "reply_send_dedup_hit" in event_types

            timeline = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/events")
            ticket_event_types = [str(item.get("event_type")) for item in timeline["items"]]
            assert "reply_send_requested" in ticket_event_types
            assert "reply_send_delivered" in ticket_event_types
            assert ticket_event_types.count("reply_send_delivered") >= 1

            trace_detail = _json(client, "GET", f"{base}/api/traces/{send_trace_id}")
            trace_event_types = [str(item.get("event_type")) for item in trace_detail["events"]]
            assert "reply_send_requested" in trace_event_types
            assert "reply_send_delivered" in trace_event_types

            observer_attempt = client.post(
                f"{base}/api/v2/tickets/{ticket.ticket_id}/reply-send",
                json={
                    "actor_id": "u_viewer_01",
                    "actor_role": "observer",
                    "content": "这条消息不应该被发送",
                    "idempotency_key": "idem-observer-blocked-001",
                },
            )
            assert observer_attempt.status_code == HTTPStatus.FORBIDDEN
            observer_payload = observer_attempt.json()
            assert observer_payload["code"] == "forbidden"
            assert "observer role cannot send replies" in observer_payload["message"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_reply_send_failure_records_retry_and_attempts(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "reply_send_api_failure.db"))
    monkeypatch.setenv("SUPPORT_AGENT_GATEWAY_LOG_PATH", str(tmp_path / "reply_send_api_failure.log"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-reply-send-002",
        thread_id="thread-reply-send-002",
        title="小区门口闸机告警",
        latest_message="闸机持续报警",
        intent="repair",
        priority="P2",
        queue="support",
        customer_id="wx_user_002",
    )

    def _always_fail_send_outbound(**_: Any) -> dict[str, Any]:
        raise ChannelAdapterError(
            channel="wecom",
            code="delivery_timeout",
            message="simulated delivery timeout",
            retryable=True,
            context={"mock": True},
        )

    runtime.gateway.send_outbound = _always_fail_send_outbound  # type: ignore[method-assign]

    server, thread = _start_server(runtime)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            first_failed = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{ticket.ticket_id}/reply-send",
                {
                    "actor_id": "u_ops_02",
                    "actor_role": "operator",
                    "content": "我们正在检查闸机告警原因，请稍候。",
                    "idempotency_key": "idem-retry-001",
                    "trace_id": "trace_reply_send_failed_001",
                },
            )
            assert first_failed["data"]["delivery_status"] == "failed"
            assert first_failed["data"]["attempt"] == 1
            assert first_failed["data"]["dedup_hit"] is False
            assert "simulated delivery timeout" in str(first_failed["data"]["error"])

            second_failed = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{ticket.ticket_id}/reply-send",
                {
                    "actor_id": "u_ops_02",
                    "actor_role": "operator",
                    "content": "我们正在检查闸机告警原因，请稍候。",
                    "idempotency_key": "idem-retry-001",
                    "trace_id": "trace_reply_send_failed_002",
                },
            )
            assert second_failed["data"]["delivery_status"] == "failed"
            assert second_failed["data"]["attempt"] == 2
            assert second_failed["data"]["dedup_hit"] is False

            timeline = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/events")
            event_types = [str(item.get("event_type")) for item in timeline["items"]]
            assert event_types.count("reply_send_failed") >= 2
            assert event_types.count("reply_send_retry_scheduled") >= 2

            reply_events = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/reply-events")
            reply_event_types = [str(item.get("event_type")) for item in reply_events["items"]]
            assert "reply_send_failed" in reply_event_types
            assert "reply_send_retry_scheduled" in reply_event_types

            trace_detail = _json(client, "GET", f"{base}/api/traces/trace_reply_send_failed_001")
            trace_event_types = [str(item.get("event_type")) for item in trace_detail["events"]]
            assert "reply_send_requested" in trace_event_types
            assert "reply_send_failed" in trace_event_types
            assert "reply_send_retry_scheduled" in trace_event_types
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
