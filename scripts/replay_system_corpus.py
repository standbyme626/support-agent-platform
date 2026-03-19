#!/usr/bin/env python3
"""十系统分发验证脚本 - 使用 replay_wecom_dispatch_bridge 验证 system 分发"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.wecom_bridge_server import process_wecom_message
from scripts.run_acceptance import build_runtime


SYSTEM_CORPUS = {
    "ticket": {
        "chat_id": "wrAEX9RgAAKNkRjmFs6f3f2z_tEPiT1A",
        "samples": [
            {"id": "ticket-001", "text": "5楼会议室空调不制冷，需要维修"},
        ],
    },
    "procurement": {
        "chat_id": "wrAEX9RgAAcu1YRglS26e-C_lKahhFLQ",
        "samples": [
            {"id": "procurement-001", "text": "申请采购2台显示器，预算已审批"},
        ],
    },
    "finance": {
        "chat_id": "wrAEX9RgAAP7aghxPD-MU6DqIx0f0WBA",
        "samples": [
            {"id": "finance-001", "text": "发票已收但付款状态异常，请财务核对"},
        ],
    },
    "approval": {
        "chat_id": "wrAEX9RgAAPG3M8WvyVfBu56nlsWy2Pw",
        "samples": [
            {"id": "approval-001", "text": "请发起加班审批流程，今晚需要处理"},
        ],
    },
    "hr": {
        "chat_id": "wrAEX9RgAAKNBDfXJKMG2UkweQ4rLCog",
        "samples": [
            {"id": "hr-001", "text": "新员工入职账号开通和工牌办理"},
        ],
    },
    "asset": {
        "chat_id": "wrAEX9RgAAg7BHbZH-wfXUQToXEoIO9g",
        "samples": [
            {"id": "asset-001", "text": "资产盘点发现设备编号缺失，需要补录"},
        ],
    },
    "kb": {
        "chat_id": "wrAEX9RgAACPv7qtmyFYQBNQ3QNGilUg",
        "samples": [
            {"id": "kb-001", "text": "知识库文档需要更新到最新版本"},
        ],
    },
    "crm": {
        "chat_id": "wrAEX9RgAAi-Hhj6vz2f-dRUo5gl-aOQ",
        "samples": [
            {"id": "crm-001", "text": "CRM case 跟进，客户线索需要分派"},
        ],
    },
    "project": {
        "chat_id": "wrAEX9RgAA6d5dHGVAYMMYdeuzVZJnbA",
        "samples": [
            {"id": "project-001", "text": "项目里程碑延期，请更新项目计划"},
        ],
    },
    "supply_chain": {
        "chat_id": "wrAEX9RgAA5hWE3NUtXZTNYFfjc4Z-4A",
        "samples": [
            {"id": "supply_chain-001", "text": "供应链收货入库异常，需确认到货数量"},
        ],
    },
}


def run_system_dispatch_validation() -> dict:
    """运行十系统分发验证"""
    runtime = build_runtime(None)
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "systems": {},
    }

    for system_key, system_data in SYSTEM_CORPUS.items():
        results["systems"][system_key] = {
            "samples": [],
            "passed": 0,
            "failed": 0,
        }

        for sample in system_data["samples"]:
            results["total"] += 1
            ts = int(time.time() * 1000000)
            trace_id = f"replay-{system_key}-{sample['id']}-{ts}"
            try:
                result = process_wecom_message(
                    runtime,
                    {
                        "msgid": f"msg-{sample['id']}-{ts}",
                        "chatid": system_data["chat_id"],
                        "chattype": "group",
                        "sender_id": f"test_user_{system_key}",
                        "text": sample["text"],
                        "req_id": trace_id,
                    },
                )

                dispatch_decision = result.as_json().get("dispatch_decision") or {}
                route = dispatch_decision.get("route", {})
                detected_system = route.get("system", "")
                matched_key = route.get("matched_key", "")
                target_group_id = route.get("target_group_id", "") or ""

                success = detected_system == system_key and bool(target_group_id)
                if success:
                    results["passed"] += 1
                    results["systems"][system_key]["passed"] += 1
                else:
                    results["failed"] += 1
                    results["systems"][system_key]["failed"] += 1

                results["systems"][system_key]["samples"].append(
                    {
                        "id": sample["id"],
                        "text": sample["text"],
                        "expected_system": system_key,
                        "expected_chat_id": system_data["chat_id"],
                        "detected_system": detected_system,
                        "matched_key": matched_key,
                        "target_group_id": target_group_id,
                        "success": success,
                    }
                )
            except Exception as e:
                results["failed"] += 1
                results["systems"][system_key]["failed"] += 1
                results["systems"][system_key]["samples"].append(
                    {
                        "id": sample["id"],
                        "text": sample["text"],
                        "expected_system": system_key,
                        "error": str(e),
                        "success": False,
                    }
                )

    return results


def main() -> int:
    print("=" * 60)
    print("十系统分发验证 - replay_wecom_dispatch_bridge")
    print("=" * 60)

    results = run_system_dispatch_validation()

    print(f"\n总计: {results['total']} 样本")
    print(f"通过: {results['passed']} | 失败: {results['failed']}")
    print(f"成功率: {results['passed'] / results['total'] * 100:.1f}%")
    print("\n" + "-" * 60)

    for system_key, system_result in results["systems"].items():
        status = "✅" if system_result["failed"] == 0 else "❌"
        print(
            f"{status} {system_key}: {system_result['passed']}/{len(system_result['samples'])} 通过"
        )

    print("\n" + "-" * 60)
    print("详细结果:")

    for system_key, system_result in results["systems"].items():
        for sample_result in system_result["samples"]:
            status = "✅" if sample_result["success"] else "❌"
            print(f"\n{status} [{sample_result['id']}] {sample_result['text'][:30]}...")
            print(
                f"   期望: {sample_result['expected_system']} → {sample_result['expected_chat_id']}"
            )
            if "error" in sample_result:
                print(f"   错误: {sample_result['error']}")
            else:
                print(
                    f"   实际: {sample_result['detected_system']} (matched: {sample_result.get('matched_key', 'N/A')})"
                    f"\n   群ID: {sample_result.get('target_group_id', 'N/A')}"
                )

    output_path = Path(__file__).parent.parent / "artifacts" / "system_dispatch_validation.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_path}")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
