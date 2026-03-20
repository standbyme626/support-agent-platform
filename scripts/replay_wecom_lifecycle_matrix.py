from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.run_acceptance import build_runtime
from scripts.wecom_bridge_server import process_wecom_message


@dataclass(frozen=True)
class LifecycleCase:
    case_id: str
    actor: str  # "customer" | "operator"
    message_template: str
    expected_action: str
    expected_usage_reason: str | None = None
    pre_resolve: bool = False
    pre_close: bool = False
    needs_target_ticket: bool = False


def _build_cases() -> list[LifecycleCase]:
    return [
        LifecycleCase("C01", "operator", "/claim {ticket_id}", "collab_claim"),
        LifecycleCase("C02", "operator", "/ claim {ticket_id}", "collab_claim"),
        LifecycleCase("C03", "operator", "认领工单 {ticket_id}", "collab_claim"),
        LifecycleCase("C04", "operator", "/take {ticket_id}", "collab_claim"),
        LifecycleCase("C05", "operator", "/pickup {ticket_id}", "collab_claim"),
        LifecycleCase("C06", "operator", "/resolve {ticket_id} 已现场恢复", "collab_resolve"),
        LifecycleCase("C07", "operator", "已解决 {ticket_id}", "collab_resolve"),
        LifecycleCase("C08", "customer", "确认已解决 {ticket_id}", "collab_customer_confirm", pre_resolve=True),
        LifecycleCase(
            "C09",
            "operator",
            "/customer-confirm {ticket_id} 用户确认恢复",
            "collab_customer_confirm",
            pre_resolve=True,
        ),
        LifecycleCase(
            "C10",
            "operator",
            "/customer-confirm {ticket_id} 用户口头确认",
            "collab_command_invalid",
            "customer_confirm_requires_resolved_state",
        ),
        LifecycleCase(
            "C11",
            "operator",
            "/operator-close {ticket_id} 用户失联 --confirm",
            "collab_operator_close",
        ),
        LifecycleCase(
            "C12",
            "operator",
            "/operator-close {ticket_id} 用户失联",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
        ),
        LifecycleCase(
            "C13",
            "operator",
            "人工关闭 {ticket_id} 用户失联",
            "collab_command_invalid",
            "natural_language_requires_slash",
        ),
        LifecycleCase(
            "C14",
            "operator",
            "/op-close {ticket_id} 兼容别名关闭 --confirm",
            "collab_operator_close",
        ),
        LifecycleCase(
            "C15",
            "operator",
            "/force-close {ticket_id} 兼容别名关闭 --confirm",
            "collab_operator_close",
        ),
        LifecycleCase(
            "C16",
            "operator",
            "/assign {ticket_id} Yusongze --confirm",
            "collab_assign",
        ),
        LifecycleCase(
            "C17",
            "operator",
            "/assign {ticket_id} Yusongze",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
        ),
        LifecycleCase(
            "C18",
            "operator",
            "/reassign {ticket_id} keguonian --confirm",
            "collab_reassign",
        ),
        LifecycleCase(
            "C19",
            "operator",
            "/reassign {ticket_id} keguonian",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
        ),
        LifecycleCase(
            "C20",
            "operator",
            "/needs-info {ticket_id} 请补充具体楼层 --confirm",
            "collab_needs_info",
        ),
        LifecycleCase(
            "C21",
            "operator",
            "/needs-info {ticket_id} 请补充具体楼层",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
        ),
        LifecycleCase(
            "C22",
            "operator",
            "/escalate {ticket_id} 影响范围扩大 --confirm",
            "collab_escalate",
        ),
        LifecycleCase(
            "C23",
            "operator",
            "/escalate {ticket_id} 影响范围扩大",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
        ),
        LifecycleCase(
            "C24",
            "operator",
            "/state {ticket_id} waiting_internal --confirm",
            "collab_state",
        ),
        LifecycleCase(
            "C25",
            "operator",
            "/state {ticket_id} waiting_internal",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
        ),
        LifecycleCase(
            "C26",
            "operator",
            "/link {ticket_id} {target_ticket_id} --confirm",
            "collab_link",
            needs_target_ticket=True,
        ),
        LifecycleCase(
            "C27",
            "operator",
            "/link {ticket_id} {target_ticket_id}",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
            needs_target_ticket=True,
        ),
        LifecycleCase(
            "C28",
            "operator",
            "/merge {ticket_id} {target_ticket_id} --confirm",
            "collab_merge",
            needs_target_ticket=True,
        ),
        LifecycleCase(
            "C29",
            "operator",
            "/merge {ticket_id} {target_ticket_id}",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
            needs_target_ticket=True,
        ),
        LifecycleCase("C30", "operator", "/priority {ticket_id} P1", "collab_priority"),
        LifecycleCase("C31", "operator", "立即处理 {ticket_id}", "collab_priority"),
        LifecycleCase("C32", "operator", "/status {ticket_id}", "collab_status"),
        LifecycleCase("C33", "operator", "/list {ticket_id} P1", "list_tickets"),
        LifecycleCase("C34", "operator", "/end-session {ticket_id} manual_end_session", "session_end"),
        LifecycleCase(
            "C35",
            "operator",
            "/close {ticket_id} 兼容关闭 --confirm",
            "collab_close_compat",
            pre_resolve=True,
        ),
        LifecycleCase(
            "C36",
            "operator",
            "/close {ticket_id} 兼容关闭",
            "collab_command_invalid",
            "high_risk_requires_confirm_flag",
            pre_resolve=True,
        ),
        LifecycleCase(
            "C37",
            "operator",
            "/close {ticket_id} 兼容关闭 --confirm",
            "collab_command_invalid",
            "customer_confirm_requires_resolved_state",
        ),
        LifecycleCase(
            "C38",
            "operator",
            "/reopen {ticket_id} 故障复发 --confirm",
            "collab_reopen",
            pre_close=True,
        ),
        LifecycleCase("C39", "operator", "/reopen {ticket_id} 故障复发", "collab_reopen", pre_close=True),
        LifecycleCase("C40", "operator", "/customerconfirm {ticket_id} 用户确认恢复", "collab_customer_confirm", pre_resolve=True),
        LifecycleCase("C41", "operator", "/endsession {ticket_id} alias_end_session", "collab_end_session"),
        LifecycleCase(
            "C42",
            "operator",
            "/operatorclose {ticket_id} 别名关闭 --confirm",
            "collab_operator_close",
        ),
        LifecycleCase(
            "C43",
            "operator",
            "/forceclose {ticket_id} 别名关闭 --confirm",
            "collab_operator_close",
        ),
        LifecycleCase("C44", "operator", "/priority {ticket_id} P2", "collab_priority"),
        LifecycleCase("C45", "operator", "查看工单列表", "list_tickets"),
        LifecycleCase("C46", "operator", "查看P1工单", "list_tickets"),
        LifecycleCase("C47", "customer", "已经恢复了，可以结单。", "collab_customer_confirm", pre_resolve=True),
        LifecycleCase("C48", "customer", "好的", "collab_customer_confirm", pre_resolve=True),
        LifecycleCase("C49", "operator", "/status {ticket_id}", "collab_status"),
        LifecycleCase("C50", "operator", "/resolve {ticket_id} 已二次复测通过", "collab_resolve"),
    ]


def _send_wecom_message(
    *,
    runtime: object,
    msgid: str,
    trace_id: str,
    chat_id: str,
    sender_id: str,
    text: str,
) -> object:
    return process_wecom_message(
        runtime,
        {
            "msgid": msgid,
            "chatid": chat_id,
            "chattype": "group",
            "sender_id": sender_id,
            "text": text,
            "req_id": trace_id,
        },
    )


def _resolve_case_customer_id(*, base_customer_id: str, case_id: str, mode: str) -> str:
    if mode == "real":
        return base_customer_id
    return f"{base_customer_id}_{case_id.lower()}"


def _resolve_private_detail_async(*, mode: str, explicit: str) -> bool:
    if explicit == "sync":
        os.environ["WECOM_GROUP_PRIVATE_DETAIL_ASYNC"] = "0"
        return False
    if explicit == "async":
        os.environ["WECOM_GROUP_PRIVATE_DETAIL_ASYNC"] = "1"
        return True
    if mode == "real":
        # One-shot replay script exits quickly; force sync avoids dropping the last DM attempt.
        os.environ["WECOM_GROUP_PRIVATE_DETAIL_ASYNC"] = "0"
        return False
    return str(os.getenv("WECOM_GROUP_PRIVATE_DETAIL_ASYNC", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay WeCom lifecycle matrix (50 cases)")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--customer-id", default="keguonian")
    parser.add_argument("--operator-id", default="Yusongze")
    parser.add_argument(
        "--customer-id-mode",
        choices=("isolated", "real"),
        default="isolated",
        help="isolated=每个用例拼接 customer_id 后缀；real=全程复用真实企微用户ID",
    )
    parser.add_argument(
        "--private-detail-mode",
        choices=("auto", "sync", "async"),
        default="auto",
        help="auto=real 模式强制 sync；isolated 模式保持环境变量",
    )
    parser.add_argument("--repair-chat-id", default="wrAEX9RgAAEuFUL3vLamRkD6m8MtU6bQ")
    parser.add_argument("--ops-chat-id", default="wrAEX9RgAAKNkRjmFs6f3f2z_tEPiT1A")
    parser.add_argument(
        "--output",
        default="artifacts/real_tests/wecom_lifecycle_matrix_report.json",
    )
    parser.add_argument(
        "--case-ids",
        default="",
        help="逗号分隔，仅回放指定用例（例如 C01,C02,C10）",
    )
    args = parser.parse_args()
    private_detail_async = _resolve_private_detail_async(
        mode=args.customer_id_mode,
        explicit=args.private_detail_mode,
    )

    runtime = build_runtime(args.env)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    cases = _build_cases()
    selected_case_ids = {
        token.strip().upper()
        for token in str(args.case_ids or "").split(",")
        if token.strip()
    }
    if selected_case_ids:
        cases = [case for case in cases if case.case_id.upper() in selected_case_ids]
    results: list[dict[str, object]] = []

    for index, case in enumerate(cases, start=1):
        case_prefix = f"lifecycle-{timestamp}-{case.case_id.lower()}"
        create_trace = f"{case_prefix}-create"
        case_customer_id = _resolve_case_customer_id(
            base_customer_id=args.customer_id,
            case_id=case.case_id,
            mode=args.customer_id_mode,
        )
        create_text = f"测试报修[{case.case_id}]：会议室投屏故障，无法显示。"
        if args.customer_id_mode == "real":
            create_text = f"新问题：{create_text}"
        created = _send_wecom_message(
            runtime=runtime,
            msgid=f"mid-{case_prefix}-create",
            trace_id=create_trace,
            chat_id=args.repair_chat_id,
            sender_id=case_customer_id,
            text=create_text,
        )
        ticket_id = str(getattr(created, "ticket_id", "") or "").strip()
        if not ticket_id:
            results.append(
                {
                    "case_id": case.case_id,
                    "passed": False,
                    "reason": "ticket_not_created",
                    "create_trace_id": create_trace,
                }
            )
            continue

        target_ticket_id = ""
        if case.needs_target_ticket:
            target_sender_id = (
                case_customer_id
                if args.customer_id_mode == "real"
                else f"{case_customer_id}_target"
            )
            target_text = f"测试报修[{case.case_id}]：备用工单，门禁异常。"
            if args.customer_id_mode == "real":
                target_text = f"新问题：{target_text}"
            target_created = _send_wecom_message(
                runtime=runtime,
                msgid=f"mid-{case_prefix}-target",
                trace_id=f"{case_prefix}-target",
                chat_id=args.repair_chat_id,
                sender_id=target_sender_id,
                text=target_text,
            )
            target_ticket_id = str(getattr(target_created, "ticket_id", "") or "").strip()
            if not target_ticket_id:
                results.append(
                    {
                        "case_id": case.case_id,
                        "ticket_id": ticket_id,
                        "passed": False,
                        "reason": "target_ticket_not_created",
                    }
                )
                continue

        if case.pre_resolve:
            _send_wecom_message(
                runtime=runtime,
                msgid=f"mid-{case_prefix}-pre-resolve",
                trace_id=f"{case_prefix}-pre-resolve",
                chat_id=args.ops_chat_id,
                sender_id=args.operator_id,
                text=f"/resolve {ticket_id} 预处理恢复",
            )
        if case.pre_close:
            _send_wecom_message(
                runtime=runtime,
                msgid=f"mid-{case_prefix}-pre-close",
                trace_id=f"{case_prefix}-pre-close",
                chat_id=args.ops_chat_id,
                sender_id=args.operator_id,
                text=f"/operator-close {ticket_id} 预关闭 --confirm",
            )

        message = case.message_template.format(
            ticket_id=ticket_id,
            target_ticket_id=target_ticket_id,
        )
        actor_id = case_customer_id if case.actor == "customer" else args.operator_id
        chat_id = args.repair_chat_id if case.actor == "customer" else args.ops_chat_id
        trace_id = f"{case_prefix}-run"
        outcome = _send_wecom_message(
            runtime=runtime,
            msgid=f"mid-{case_prefix}-run",
            trace_id=trace_id,
            chat_id=chat_id,
            sender_id=actor_id,
            text=message,
        )

        actual_action = str(getattr(outcome, "ticket_action", "") or "")
        actual_status = str(getattr(outcome, "status", "") or "")
        reply_text = str(getattr(outcome, "reply_text", "") or "")
        usage_reason = None
        try:
            usage_reason = str((getattr(outcome, "as_json")() or {}).get("reply_trace", {}).get("usage_reason") or "")
        except Exception:
            usage_reason = ""
        if not usage_reason:
            rt = getattr(outcome, "reply_trace", None)
            if isinstance(rt, dict):
                usage_reason = str(rt.get("usage_reason") or "")
        if not usage_reason:
            if "请追加确认标记" in reply_text:
                usage_reason = "high_risk_requires_confirm_flag"
            elif "请使用显式命令" in reply_text:
                usage_reason = "natural_language_requires_slash"
            elif "不能直接确认关闭" in reply_text:
                usage_reason = "customer_confirm_requires_resolved_state"

        failures: list[str] = []
        if actual_status != "ok":
            failures.append(f"status={actual_status}")
        if actual_action != case.expected_action:
            failures.append(f"ticket_action={actual_action} expected={case.expected_action}")
        expected_usage = str(case.expected_usage_reason or "")
        if expected_usage and usage_reason != expected_usage:
            failures.append(f"usage_reason={usage_reason or 'none'} expected={expected_usage}")

        results.append(
            {
                "index": index,
                "case_id": case.case_id,
                "ticket_id": ticket_id,
                "target_ticket_id": target_ticket_id or None,
                "actor": case.actor,
                "message": message,
                "expected_action": case.expected_action,
                "actual_action": actual_action,
                "expected_usage_reason": case.expected_usage_reason,
                "actual_usage_reason": usage_reason or None,
                "trace_id": trace_id,
                "passed": not failures,
                "failures": failures,
            }
        )

    passed = sum(1 for item in results if bool(item.get("passed")))
    failed = len(results) - passed
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": args.env,
        "customer_id": args.customer_id,
        "operator_id": args.operator_id,
        "customer_id_mode": args.customer_id_mode,
        "private_detail_mode": args.private_detail_mode,
        "private_detail_async_effective": private_detail_async,
        "selected_case_ids": sorted(selected_case_ids) if selected_case_ids else None,
        "repair_chat_id": args.repair_chat_id,
        "ops_chat_id": args.ops_chat_id,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
