from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .priority_detector import TicketPriority

LLM_PRIORITY_PROMPT = """判断以下工单的紧急优先级。

工单描述: {message_text}

优先级规则:
- P1: 生命安全、重大故障、立即处理。如：燃气泄漏、火灾、系统崩溃、人员受伤
- P2: 影响工作、故障、需要尽快处理。如：打印机坏了、门禁异常、影响办公
- P3: 普通问题、日常维护。如：空调不制冷、网络慢、设备建议
- P4: 建议、优化、低优先级。如：功能建议、体验改进

返回格式（仅返回一行）:
P1:理由
或
P2:理由

例如: P1:涉及燃气泄漏风险"""


@dataclass
class LLMPriorityResult:
    priority: TicketPriority
    reason: str
    confidence: float
    model: str
    updated_at: datetime


async def detect_priority_with_llm(
    message_text: str,
    current_priority: str | None = None,
) -> LLMPriorityResult | None:
    """异步调用 LLM 判断工单优先级"""

    llm_enabled = os.environ.get("LLM_ENABLED", "0") == "1"
    if not llm_enabled:
        return None

    try:
        from core.llm_client import LLMClient
    except ImportError:
        return None

    try:
        client = LLMClient()
        model = os.environ.get("LLM_PRIORITY_MODEL", "gpt-4o-mini")

        prompt = LLM_PRIORITY_PROMPT.format(message_text=message_text)
        response = await client.agenerate(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()

        priority = "P3"
        reason = "LLM判断"

        if content.startswith("P1"):
            priority = "P1"
            reason = content[2:].strip() or "LLM判断为P1"
        elif content.startswith("P2"):
            priority = "P2"
            reason = content[2:].strip() or "LLM判断为P2"
        elif content.startswith("P3"):
            priority = "P3"
            reason = content[2:].strip() or "LLM判断为P3"
        elif content.startswith("P4"):
            priority = "P4"
            reason = content[2:].strip() or "LLM判断为P4"

        return LLMPriorityResult(
            priority=priority,
            reason=reason[:200] if reason else "LLM判断",
            confidence=0.85,
            model=model,
            updated_at=datetime.now(),
        )

    except Exception:
        return None


def sync_detect_priority_with_llm(
    message_text: str,
    current_priority: str | None = None,
) -> LLMPriorityResult | None:
    """同步版本（用于测试）"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return None
        return loop.run_until_complete(detect_priority_with_llm(message_text, current_priority))
    except Exception:
        return None
