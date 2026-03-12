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


def test_ticket_actions_chain_and_timeline(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_actions_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-ticket-actions-001",
        thread_id="thread-ticket-actions-001",
        title="门禁故障",
        latest_message="刷卡没反应",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            detail = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}")
            assert detail["data"]["status"] == "open"

            claimed = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/claim",
                {"actor_id": "u_ops_01"},
            )
            assert claimed["data"]["status"] == "pending"
            assert claimed["data"]["assignee"] == "u_ops_01"

            reassigned = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/reassign",
                {
                    "actor_id": "u_ops_01",
                    "target_queue": "billing",
                    "target_assignee": "u_ops_02",
                },
            )
            assert reassigned["data"]["queue"] == "billing"
            assert reassigned["data"]["assignee"] == "u_ops_02"

            escalated = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/escalate",
                {"actor_id": "u_ops_02", "note": "need supervisor"},
            )
            assert escalated["data"]["status"] == "pending"
            assert escalated["data"]["handoff_state"] == "pending_approval"
            approval_id = str(escalated["data"]["approval_id"])
            assert approval_id

            pending = _json(client, "GET", f"{base}/api/approvals/pending?page=1&page_size=20")
            pending_ids = {item["approval_id"] for item in pending["items"]}
            assert approval_id in pending_ids

            approved = _json(
                client,
                "POST",
                f"{base}/api/approvals/{approval_id}/approve",
                {"actor_id": "u_supervisor_01", "note": "approved"},
            )
            assert approved["data"]["status"] == "escalated"

            resolved = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/resolve",
                {
                    "actor_id": "u_ops_02",
                    "resolution_note": "已远程重启",
                    "resolution_code": "remote_reboot",
                },
            )
            assert resolved["data"]["status"] == "resolved"

            closed = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/close",
                {
                    "actor_id": "u_ops_02",
                    "resolution_note": "客户确认恢复",
                    "close_reason": "customer_confirmed",
                },
            )
            assert closed["data"]["status"] == "closed"

            events = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/events")
            event_types = {item["event_type"] for item in events["items"]}
            assert "ticket_assigned" in event_types
            assert "ticket_reassign_requested" in event_types
            assert "approval_requested" in event_types
            assert "approval_decision" in event_types
            assert "ticket_resolved" in event_types
            assert "ticket_closed" in event_types

            for item in events["items"]:
                assert item["actor_id"]
                assert item["created_at"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_approval_reject_and_timeout_paths(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv(
        "SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_approval_reject_timeout.db")
    )
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    ticket = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-ticket-approval-002",
        thread_id="thread-ticket-approval-002",
        title="停车场道闸故障",
        latest_message="道闸无法抬杆",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            first_request = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/escalate",
                {"actor_id": "u_ops_01", "note": "need supervisor"},
            )
            approval_id = str(first_request["data"]["approval_id"])
            assert approval_id

            rejected = _json(
                client,
                "POST",
                f"{base}/api/approvals/{approval_id}/reject",
                {"actor_id": "u_supervisor_01", "note": "insufficient context"},
            )
            assert rejected["approval"]["status"] == "rejected"

            timeout_request = _json(
                client,
                "POST",
                f"{base}/api/tickets/{ticket.ticket_id}/escalate",
                {"actor_id": "u_ops_01", "note": "need supervisor", "timeout_minutes": 0},
            )
            assert timeout_request["data"]["status"] == "open"
            assert timeout_request["data"]["handoff_state"] == "pending_approval"

            pending = _json(client, "GET", f"{base}/api/approvals/pending?page=1&page_size=20")
            assert pending["items"] == []

            actions = _json(client, "GET", f"{base}/api/tickets/{ticket.ticket_id}/pending-actions")
            statuses = {item["status"] for item in actions["items"]}
            assert {"rejected", "timeout"}.issubset(statuses)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_duplicate_merge_suggestion_flow(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_duplicate_merge_api.db"))
    monkeypatch.setenv("SUPPORT_AGENT_GATEWAY_LOG_PATH", str(tmp_path / "ticket_duplicate_merge_api.log"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    source = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-dup-001",
        thread_id="thread-dup-001",
        title="停车场抬杆故障",
        latest_message="停车场道闸抬杆失败，车辆无法出场",
        intent="repair",
        priority="P2",
        queue="support",
    )
    target = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-dup-001",
        thread_id="thread-dup-001",
        title="停车场抬杆故障再次报修",
        latest_message="道闸抬杆还是失败，跟上一条是同一个故障",
        intent="repair",
        priority="P2",
        queue="support",
    )

    reject_source = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-dup-002",
        thread_id="thread-dup-002",
        title="电梯异响故障",
        latest_message="电梯持续异响，怀疑电机问题",
        intent="repair",
        priority="P2",
        queue="support",
    )
    reject_target = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-dup-002",
        thread_id="thread-dup-002",
        title="电梯异响问题复现",
        latest_message="电梯异响再次出现，和昨天一样",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            duplicates = _json(client, "GET", f"{base}/api/tickets/{source.ticket_id}/duplicates")
            duplicate_ids = {str(item["ticket_id"]) for item in duplicates["items"]}
            assert target.ticket_id in duplicate_ids

            accepted = _json(
                client,
                "POST",
                f"{base}/api/tickets/{source.ticket_id}/merge-suggestion/accept",
                {
                    "actor_id": "u_ops_03",
                    "duplicate_ticket_id": target.ticket_id,
                    "trace_id": "trace_merge_accept_001",
                    "note": "重复报修，合并处理",
                },
            )
            assert accepted["data"]["status"] == "closed"
            assert accepted["data"]["metadata"]["merged_into_ticket_id"] == target.ticket_id

            source_events = _json(client, "GET", f"{base}/api/tickets/{source.ticket_id}/events")
            assert "merge_suggestion_accepted" in {item["event_type"] for item in source_events["items"]}
            target_events = _json(client, "GET", f"{base}/api/tickets/{target.ticket_id}/events")
            assert "duplicate_merged_in" in {item["event_type"] for item in target_events["items"]}

            accept_trace = runtime.trace_logger.query_by_trace("trace_merge_accept_001", limit=200)
            assert any(str(item.get("event_type")) == "merge_suggestion_accepted" for item in accept_trace)

            rejected = _json(
                client,
                "POST",
                f"{base}/api/tickets/{reject_source.ticket_id}/merge-suggestion/reject",
                {
                    "actor_id": "u_ops_04",
                    "duplicate_ticket_id": reject_target.ticket_id,
                    "trace_id": "trace_merge_reject_001",
                    "note": "语义接近但并非同单",
                },
            )
            assert rejected["data"]["status"] == "open"
            assert rejected["data"]["metadata"]["merge_state"] == "rejected"

            reject_events = _json(client, "GET", f"{base}/api/tickets/{reject_source.ticket_id}/events")
            assert "merge_suggestion_rejected" in {item["event_type"] for item in reject_events["items"]}
            reject_trace = runtime.trace_logger.query_by_trace("trace_merge_reject_001", limit=200)
            assert any(str(item.get("event_type")) == "merge_suggestion_rejected" for item in reject_trace)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
