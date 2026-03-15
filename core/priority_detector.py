from __future__ import annotations

from typing import Literal

TicketPriority = Literal["P1", "P2", "P3", "P4"]

PRIORITY_KEYWORDS = {
    "P1": (
        "紧急",
        "非常紧急",
        "十万火急",
        "立即处理",
        "马上处理",
        "urgent",
        "critical",
        "asap",
        "煤气泄露",
        "燃气泄露",
        "天然气泄露",
        "煤气管泄露",
        "燃气泄漏",
        "燃气漏",
        "燃气管道",
        "管道泄露",
        "管道泄漏",
        "漏气",
        "煤气泄漏",
        "火灾",
        "着火",
        "爆炸",
        "有人受伤",
        "生命危险",
        "安全风险",
        "重大故障",
        "系统崩溃",
        "宕机",
        "down",
        "停止运行",
        "停止工作",
        "全面瘫痪",
        "停止服务",
        "服务不可用",
    ),
    "P2": (
        "加急",
        "尽快处理",
        "优先处理",
        "尽快",
        "比较紧急",
        "important",
        "high",
        "严重",
        "影响工作",
        "无法使用",
        "损坏",
        "故障",
        "坏了",
        "不工作",
        "停止",
        "罢工",
        "报错",
        "错误",
        "异常",
    ),
    "P3": (
        "普通",
        "一般",
        "正常",
        "普通问题",
        "普通故障",
        "normal",
        "medium",
        "普通处理",
        "常规",
        "日常",
    ),
    "P4": (
        "不急",
        "不紧急",
        "稍后",
        "以后处理",
        "低优先级",
        "建议",
        "改进",
        "优化",
        "enhancement",
        "low",
        "想法",
        "功能建议",
        "改进建议",
    ),
}

URGENT_KEYWORDS = (
    "紧急",
    "非常紧急",
    "十万火急",
    "立即",
    "马上",
    "急",
    "urgent",
    "critical",
    "asap",
    "重要",
    "重要紧急",
)


def detect_ticket_priority(message_text: str) -> TicketPriority:
    if not message_text:
        return "P3"

    text_lower = message_text.lower()

    for keyword in PRIORITY_KEYWORDS["P1"]:
        if keyword.lower() in text_lower:
            return "P1"

    for keyword in PRIORITY_KEYWORDS["P2"]:
        if keyword.lower() in text_lower:
            return "P2"

    for keyword in PRIORITY_KEYWORDS["P4"]:
        if keyword.lower() in text_lower:
            return "P4"

    return "P3"


def detect_urgency_level(message_text: str) -> str:
    if not message_text:
        return "normal"

    text_lower = message_text.lower()

    for keyword in PRIORITY_KEYWORDS["P1"]:
        if keyword.lower() in text_lower:
            return "critical"

    for keyword in PRIORITY_KEYWORDS["P2"]:
        if keyword.lower() in text_lower:
            return "high"

    for keyword in PRIORITY_KEYWORDS["P4"]:
        if keyword.lower() in text_lower:
            return "low"

    return "normal"
