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


def test_session_api_supports_active_switch_and_new_issue(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "session_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    first = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-session-api-001",
        thread_id="thread-session-api-001",
        title="停车场道闸故障",
        latest_message="抬杆失败",
        intent="repair",
        priority="P2",
        queue="support",
    )
    second = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-session-api-001",
        thread_id="thread-session-api-001",
        title="电梯异响问题",
        latest_message="电梯持续异响",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            session_detail = _json(client, "GET", f"{base}/api/sessions/sess-session-api-001")
            assert session_detail["data"]["active_ticket_id"] == second.ticket_id
            assert first.ticket_id in session_detail["data"]["recent_ticket_ids"]

            session_tickets = _json(
                client,
                "GET",
                f"{base}/api/sessions/sess-session-api-001/tickets",
            )
            ticket_ids = [item["ticket_id"] for item in session_tickets["items"]]
            assert ticket_ids[:2] == [second.ticket_id, first.ticket_id]

            disambiguated = _json(
                client,
                "POST",
                f"{base}/api/copilot/disambiguate",
                {
                    "session_id": "sess-session-api-001",
                    "message_text": "帮我看看",
                },
            )
            disambiguated_data = disambiguated["data"]
            assert disambiguated_data["decision"] == "awaiting_disambiguation"
            assert disambiguated_data["active_ticket_id"] == second.ticket_id
            assert disambiguated_data["session"]["session_mode"] == "awaiting_disambiguation"
            assert isinstance(disambiguated_data["confidence"], float)
            assert isinstance(disambiguated_data["reason"], str)
            assert isinstance(disambiguated_data["intent"], dict)
            assert isinstance(disambiguated_data["candidate_tickets"], list)
            assert isinstance(disambiguated_data["options"], list)
            option_actions = [item["action"] for item in disambiguated_data["options"]]
            assert "create_new" in option_actions
            assert {"session_id", "message_text", "decision", "confidence", "reason"}.issubset(
                disambiguated_data.keys()
            )

            new_command = _json(
                client,
                "POST",
                f"{base}/api/copilot/disambiguate",
                {
                    "session_id": "sess-session-api-001",
                    "message_text": "/new 继续当前问题",
                    "actor_id": "u_ops_01",
                    "trace_id": "trace_session_new_command_001",
                },
            )
            new_command_data = new_command["data"]
            assert new_command_data["decision"] == "new_issue_detected"
            assert new_command_data["session_action"] == "new_issue"
            assert new_command_data["reason"] == "explicit_new_command"
            assert new_command_data["session"]["active_ticket_id"] is None
            assert new_command_data["session"]["session_mode"] == "awaiting_new_issue"
            assert (
                new_command_data["session_action_result"]["trace_id"]
                == "trace_session_new_command_001"
            )

            switched = _json(
                client,
                "POST",
                f"{base}/api/tickets/{first.ticket_id}/switch-active",
                {"actor_id": "u_ops_01"},
            )
            assert switched["data"]["session"]["active_ticket_id"] == first.ticket_id

            after_switch = _json(client, "GET", f"{base}/api/sessions/sess-session-api-001")
            assert after_switch["data"]["active_ticket_id"] == first.ticket_id
            assert second.ticket_id in after_switch["data"]["recent_ticket_ids"]

            end_phrase = _json(
                client,
                "POST",
                f"{base}/api/copilot/disambiguate",
                {
                    "session_id": "sess-session-api-001",
                    "message_text": "这轮先到这里，结束当前对话",
                    "actor_id": "u_ops_01",
                    "trace_id": "trace_session_end_phrase_001",
                },
            )
            end_phrase_data = end_phrase["data"]
            assert end_phrase_data["session_action"] == "session_end"
            assert end_phrase_data["reason"] == "chinese_end_phrase"
            assert end_phrase_data["session"]["active_ticket_id"] is None
            assert end_phrase_data["session"]["session_mode"] == "awaiting_new_issue"
            assert (
                end_phrase_data["session_action_result"]["trace_id"]
                == "trace_session_end_phrase_001"
            )

            new_issue = _json(
                client,
                "POST",
                f"{base}/api/sessions/sess-session-api-001/new-issue",
                {"actor_id": "u_ops_01"},
            )
            assert new_issue["data"]["active_ticket_id"] is None
            assert any(
                ticket_id in new_issue["data"]["recent_ticket_ids"]
                for ticket_id in {first.ticket_id, second.ticket_id}
            )
            assert new_issue["data"]["session_mode"] == "awaiting_new_issue"

            reset = _json(
                client,
                "POST",
                f"{base}/api/sessions/sess-session-api-001/reset",
                {"actor_id": "u_ops_01"},
            )
            assert reset["data"]["active_ticket_id"] is None
            assert reset["data"]["session_mode"] == "awaiting_new_issue"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
