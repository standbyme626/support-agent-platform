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
            assert isinstance(escalated["data"]["collab_graph"], dict)
            assert escalated["data"]["collab_graph"]["approval_status"] == "pending_approval"
            assert isinstance(escalated["data"]["collab_graph"].get("pause_checkpoint_id"), str)

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
            assert approved["collab_graph"]["approval_status"] == "approved"
            assert approved["collab_graph"]["result_action"] == "escalate"

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
            assert rejected["collab_graph"]["approval_status"] == "rejected"
            assert rejected["collab_graph"]["result_action"] == "rejected"

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
    monkeypatch.setenv(
        "SUPPORT_AGENT_GATEWAY_LOG_PATH",
        str(tmp_path / "ticket_duplicate_merge_api.log"),
    )
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
            assert "merge_suggestion_accepted" in {
                item["event_type"] for item in source_events["items"]
            }
            target_events = _json(client, "GET", f"{base}/api/tickets/{target.ticket_id}/events")
            assert "duplicate_merged_in" in {item["event_type"] for item in target_events["items"]}

            accept_trace = runtime.trace_logger.query_by_trace("trace_merge_accept_001", limit=200)
            assert any(
                str(item.get("event_type")) == "merge_suggestion_accepted"
                for item in accept_trace
            )

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

            reject_events = _json(
                client,
                "GET",
                f"{base}/api/tickets/{reject_source.ticket_id}/events",
            )
            assert "merge_suggestion_rejected" in {
                item["event_type"] for item in reject_events["items"]
            }
            reject_trace = runtime.trace_logger.query_by_trace("trace_merge_reject_001", limit=200)
            assert any(
                str(item.get("event_type")) == "merge_suggestion_rejected"
                for item in reject_trace
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_v2_actions_and_v1_close_control_and_v2_intake_investigate(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ticket_actions_v2_api.db"))
    monkeypatch.setenv("LLM_ENABLED", "0")

    runtime = build_runtime("dev")
    v2_customer = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-v2-actions-001",
        thread_id="thread-v2-actions-001",
        title="门禁设备故障",
        latest_message="刷卡无反应",
        intent="repair",
        priority="P2",
        queue="support",
    )
    v2_operator = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-v2-actions-002",
        thread_id="thread-v2-actions-002",
        title="停车场道闸异常",
        latest_message="道闸无法关闭",
        intent="repair",
        priority="P2",
        queue="support",
    )
    v1_close = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-v1-close-003",
        thread_id="thread-v1-close-003",
        title="电梯异响",
        latest_message="电梯持续异响",
        intent="repair",
        priority="P2",
        queue="support",
    )
    v1_close_reason = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-v1-close-005",
        thread_id="thread-v1-close-005",
        title="地库照明异常",
        latest_message="地库灯光闪烁",
        intent="repair",
        priority="P2",
        queue="support",
    )
    v2_investigate = runtime.ticket_api.create_ticket(
        channel="wecom",
        session_id="sess-v2-investigate-004",
        thread_id="thread-v2-investigate-004",
        title="空调不制冷",
        latest_message="中央空调不制冷且风量很小",
        intent="repair",
        priority="P2",
        queue="support",
    )

    server, thread = _start_server("dev")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            resolved = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{v2_customer.ticket_id}/resolve",
                {
                    "actor_id": "u_ops_11",
                    "resolution_note": "远程重启后已恢复",
                    "resolution_code": "remote_reboot",
                    "trace_id": "trace_v2_resolve_001",
                },
            )
            assert resolved["data"]["status"] == "resolved"
            assert resolved["data"]["event_type"] == "ticket_resolved"
            assert resolved["data"]["resolved_action"] == "resolve"
            assert resolved["data"]["trace_id"] == "trace_v2_resolve_001"

            customer_confirmed = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{v2_customer.ticket_id}/customer-confirm",
                {
                    "actor_id": "u_ops_11",
                    "note": "客户确认恢复",
                    "trace_id": "trace_v2_customer_confirm_001",
                },
            )
            assert customer_confirmed["data"]["status"] == "closed"
            assert customer_confirmed["data"]["event_type"] == "ticket_customer_confirmed"
            assert customer_confirmed["data"]["resolved_action"] == "customer-confirm"
            assert customer_confirmed["data"]["trace_id"] == "trace_v2_customer_confirm_001"

            operator_closed = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{v2_operator.ticket_id}/operator-close",
                {
                    "actor_id": "u_ops_12",
                    "reason": "operator_forced_close",
                    "note": "人工确认现场恢复，先行闭环",
                    "trace_id": "trace_v2_operator_close_001",
                },
            )
            assert operator_closed["data"]["status"] == "closed"
            assert operator_closed["data"]["event_type"] == "ticket_operator_closed"
            assert operator_closed["data"]["resolved_action"] == "operator-close"
            assert operator_closed["data"]["trace_id"] == "trace_v2_operator_close_001"

            _json(
                client,
                "POST",
                f"{base}/api/tickets/{v1_close.ticket_id}/resolve",
                {
                    "actor_id": "u_ops_13",
                    "resolution_note": "已给出恢复方案",
                    "trace_id": "trace_v1_resolve_001",
                },
            )
            ambiguous = client.post(
                f"{base}/api/tickets/{v1_close.ticket_id}/close",
                json={
                    "actor_id": "u_ops_13",
                    "resolution_note": "关闭工单",
                    "trace_id": "trace_v1_close_ambiguous_001",
                },
            )
            assert ambiguous.status_code == 400
            ambiguous_payload = ambiguous.json()
            assert ambiguous_payload["code"] == "invalid_payload"
            assert "ambiguous close action" in ambiguous_payload["message"]

            _json(
                client,
                "POST",
                f"{base}/api/tickets/{v1_close_reason.ticket_id}/resolve",
                {
                    "actor_id": "u_ops_15",
                    "resolution_note": "已确认线路恢复",
                    "trace_id": "trace_v1_reason_resolve_001",
                },
            )
            conflicting = client.post(
                f"{base}/api/tickets/{v1_close_reason.ticket_id}/close",
                json={
                    "actor_id": "u_ops_15",
                    "action": "customer_confirm",
                    "close_reason": "operator_forced_close",
                    "trace_id": "trace_v1_close_conflict_001",
                },
            )
            assert conflicting.status_code == 400
            conflicting_payload = conflicting.json()
            assert conflicting_payload["code"] == "invalid_payload"
            assert "conflicting close action" in conflicting_payload["message"]

            deterministic_reason_close = _json(
                client,
                "POST",
                f"{base}/api/tickets/{v1_close_reason.ticket_id}/close",
                {
                    "actor_id": "u_ops_15",
                    "close_reason": "manual_close",
                    "resolution_note": "按运维规则关单",
                    "trace_id": "trace_v1_close_reasoned_001",
                },
            )
            assert deterministic_reason_close["data"]["status"] == "closed"
            assert deterministic_reason_close["data"]["resolved_action"] == "operator_close"
            assert deterministic_reason_close["data"]["trace_id"] == "trace_v1_close_reasoned_001"

            controlled_close = _json(
                client,
                "POST",
                f"{base}/api/tickets/{v1_close.ticket_id}/close",
                {
                    "actor_id": "u_ops_13",
                    "action": "customer_confirm",
                    "resolution_note": "客户确认关闭",
                    "trace_id": "trace_v1_close_controlled_001",
                },
            )
            assert controlled_close["data"]["status"] == "closed"
            assert controlled_close["data"]["resolved_action"] == "customer_confirm"
            assert controlled_close["data"]["trace_id"] == "trace_v1_close_controlled_001"

            investigate_trace_id = "trace_v2_investigate_001"
            investigated = _json(
                client,
                "POST",
                f"{base}/api/v2/tickets/{v2_investigate.ticket_id}/investigate",
                {
                    "actor_id": "u_ops_14",
                    "question": "请给出根因分析建议与下一步动作",
                    "trace_id": investigate_trace_id,
                },
            )
            assert investigated["data"]["advice_only"] is True
            assert investigated["data"]["investigation"]["safety"]["advice_only"] is True
            assert investigated["data"]["trace"]["trace_id"] == investigate_trace_id

            intake_trace_id = "trace_v2_intake_run_001"
            intake_result = _json(
                client,
                "POST",
                f"{base}/api/v2/intake/run",
                {
                    "session_id": v2_investigate.session_id,
                    "text": "空调异常，用户要求尽快处理",
                    "channel": "wecom",
                    "trace_id": intake_trace_id,
                    "metadata": {
                        "ticket_id": v2_investigate.ticket_id,
                        "actor_id": "u_ops_14",
                        "force_investigation": True,
                    },
                },
            )
            assert intake_result["data"]["trace"]["trace_id"] == intake_trace_id
            assert intake_result["data"]["advice_only"] is True
            assert intake_result["data"]["high_risk_action_executed"] is False
            assert intake_result["data"]["runtime_graph"] == "intake_graph_v1"
            assert isinstance(intake_result["data"]["runtime_current_node"], str)
            assert isinstance(intake_result["data"]["runtime_path"], list)
            assert isinstance(intake_result["data"]["runtime_state"], dict)
            assert isinstance(intake_result["data"]["result"]["trace"]["steps"], list)
            assert intake_result["data"]["result"]["trace"]["steps"]

            intake_new_trace_id = "trace_v2_intake_new_command_001"
            intake_new_result = _json(
                client,
                "POST",
                f"{base}/api/v2/intake/run",
                {
                    "session_id": v2_investigate.session_id,
                    "text": "/new 继续当前问题",
                    "channel": "wecom",
                    "trace_id": intake_new_trace_id,
                    "metadata": {
                        "ticket_id": v2_investigate.ticket_id,
                        "actor_id": "u_ops_14",
                    },
                },
            )
            assert intake_new_result["data"]["trace"]["trace_id"] == intake_new_trace_id
            assert intake_new_result["data"]["advice_only"] is True
            assert intake_new_result["data"]["high_risk_action_executed"] is False
            assert intake_new_result["data"]["runtime_state"]["session_action"] == "new_issue"
            assert (
                intake_new_result["data"]["result"]["session_action"]["action"] == "new_issue"
            )
            assert (
                intake_new_result["data"]["result"]["session_action"]["result"]["session"][
                    "session_mode"
                ]
                == "awaiting_new_issue"
            )

            intake_end_trace_id = "trace_v2_intake_end_phrase_001"
            intake_end_result = _json(
                client,
                "POST",
                f"{base}/api/v2/intake/run",
                {
                    "session_id": v2_investigate.session_id,
                    "text": "这轮先到这里，结束当前对话",
                    "channel": "wecom",
                    "trace_id": intake_end_trace_id,
                    "metadata": {
                        "ticket_id": v2_investigate.ticket_id,
                        "actor_id": "u_ops_14",
                    },
                },
            )
            assert intake_end_result["data"]["trace"]["trace_id"] == intake_end_trace_id
            assert intake_end_result["data"]["advice_only"] is True
            assert intake_end_result["data"]["high_risk_action_executed"] is False
            assert intake_end_result["data"]["runtime_state"]["session_action"] == "session_end"
            assert (
                intake_end_result["data"]["result"]["session_action"]["action"] == "session_end"
            )
            assert (
                intake_end_result["data"]["result"]["session_action"]["result"]["event_type"]
                == "session_ended"
            )

            session_end = _json(
                client,
                "POST",
                f"{base}/api/v2/sessions/{v2_investigate.session_id}/end",
                {
                    "actor_id": "u_ops_14",
                    "reason": "manual_end",
                    "trace_id": "trace_v2_session_end_001",
                },
            )
            assert session_end["data"]["event_type"] == "session_ended"
            assert session_end["data"]["trace_id"] == "trace_v2_session_end_001"
            assert session_end["data"]["session"]["active_ticket_id"] is None

            investigate_trace = runtime.trace_logger.query_by_trace(investigate_trace_id, limit=100)
            assert any(
                str(item.get("event_type")) == "ticket_investigation_v2"
                for item in investigate_trace
            )
            intake_trace = runtime.trace_logger.query_by_trace(intake_trace_id, limit=100)
            assert any(str(item.get("event_type")) == "intake_run_v2" for item in intake_trace)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
