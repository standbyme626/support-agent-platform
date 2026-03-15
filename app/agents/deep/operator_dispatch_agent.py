from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CopilotQueryContext:
    query: str
    actor_id: str


class OperatorSupervisorAgent:
    """Queue/SLA advisory agent. Produces advice-only outputs with runtime trace."""

    def __init__(
        self,
        *,
        read_dashboard_summary_tool: Callable[..., Any] | None = None,
        read_queue_summary_tool: Callable[..., Any] | None = None,
        search_grounding_tool: Callable[..., Any] | None = None,
    ) -> None:
        self._read_dashboard_summary_tool = read_dashboard_summary_tool
        self._read_queue_summary_tool = read_queue_summary_tool
        self._search_grounding_tool = search_grounding_tool

    def analyze(self, query: str, *, actor_id: str = "ops-api") -> dict[str, Any]:
        context = CopilotQueryContext(query=query, actor_id=actor_id)
        dashboard_summary = _safe_tool_call(self._read_dashboard_summary_tool) or {}
        queue_summary = _safe_tool_call(self._read_queue_summary_tool) or []
        grounding_sources = _safe_tool_call(self._search_grounding_tool, query=query) or []
        runtime_trace = _runtime_trace(
            agent="operator_supervisor_agent_v1",
            mode="deep-agent",
            tool_calls=[
                {"tool": "dashboard.summary", "ok": isinstance(dashboard_summary, dict)},
                {"tool": "queue.summary", "ok": isinstance(queue_summary, list)},
                {"tool": "retriever.grounded_search", "ok": isinstance(grounding_sources, list)},
            ],
            policy_gate={
                "enforced": True,
                "blocked_execution": True,
                "disallowed_actions": ["reassign", "resolve", "operator-close", "approve"],
            },
        )
        recommended_actions = _operator_recommended_actions(dashboard_summary, queue_summary)
        confidence = _confidence_score(
            grounding_count=len(grounding_sources),
            recommendation_count=len(recommended_actions),
        )
        in_progress = _int_value(dashboard_summary.get("in_progress_count"))
        sla_warning = _int_value(dashboard_summary.get("sla_warning_count"))
        sla_breached = _int_value(dashboard_summary.get("sla_breached_count"))
        escalated = _int_value(dashboard_summary.get("escalated_count"))
        answer = (
            f"Operator建议：当前处理中{in_progress}单，SLA预警{sla_warning}单，"
            f"SLA违约{sla_breached}单，升级{escalated}单。优先处理高风险队列。"
        )
        return {
            "scope": "operator",
            "query": context.query,
            "answer": answer,
            "advice_only": True,
            "dashboard_summary": dashboard_summary,
            "grounding_sources": grounding_sources,
            "recommended_actions": recommended_actions,
            "confidence": confidence,
            "runtime_trace": runtime_trace,
            "generated_at": datetime.now(UTC).isoformat(),
        }


class DispatchCollaborationAgent:
    """Dispatch advisory agent. Suggests routing only and never executes transitions."""

    _TERMINAL_HINTS = ("reassign", "resolve", "operator-close", "close", "执行", "关闭")

    def __init__(
        self,
        *,
        read_queue_summary_tool: Callable[..., Any] | None = None,
        search_grounding_tool: Callable[..., Any] | None = None,
    ) -> None:
        self._read_queue_summary_tool = read_queue_summary_tool
        self._search_grounding_tool = search_grounding_tool

    def analyze(self, query: str, *, actor_id: str = "ops-api") -> dict[str, Any]:
        context = CopilotQueryContext(query=query, actor_id=actor_id)
        queue_summary = _safe_tool_call(self._read_queue_summary_tool) or []
        priorities = sorted(
            list(queue_summary),
            key=lambda item: (
                _int_value(item.get("escalated_count")),
                _int_value(item.get("breached_count")),
                _int_value(item.get("warning_count")),
                _int_value(item.get("in_progress_count")),
            ),
            reverse=True,
        )
        grounding_sources = _safe_tool_call(self._search_grounding_tool, query=query) or []
        blocked_execution = _contains_terminal_action_request(query)
        top_queue = str(priorities[0].get("queue_name")) if priorities else "n/a"
        answer = (
            f"Dispatch建议：优先向队列 {top_queue} 分配处理资源，并优先处理升级与SLA风险工单。"
            if priorities
            else "Dispatch建议：暂无可调度队列数据。"
        )
        if blocked_execution:
            answer = (
                "Dispatch仅提供建议，不直接执行终态动作。"
                f" 当前建议优先关注队列 {top_queue} 并由人工执行审批后的动作。"
            )
        recommended_actions = _dispatch_recommended_actions(priorities)
        confidence = _confidence_score(
            grounding_count=len(grounding_sources),
            recommendation_count=len(recommended_actions),
        )
        runtime_trace = _runtime_trace(
            agent="dispatch_collaboration_agent_v1",
            mode="graph-gated",
            tool_calls=[
                {"tool": "queue.summary", "ok": isinstance(queue_summary, list)},
                {"tool": "retriever.grounded_search", "ok": isinstance(grounding_sources, list)},
            ],
            policy_gate={
                "enforced": True,
                "blocked_execution": blocked_execution,
                "disallowed_actions": ["reassign", "resolve", "operator-close", "approve"],
            },
        )
        return {
            "scope": "dispatch",
            "query": context.query,
            "answer": answer,
            "advice_only": True,
            "dispatch_priority": priorities[:5],
            "grounding_sources": grounding_sources,
            "recommended_actions": recommended_actions,
            "confidence": confidence,
            "runtime_trace": runtime_trace,
            "generated_at": datetime.now(UTC).isoformat(),
        }


def build_operator_supervisor_agent(
    *,
    read_dashboard_summary_tool: Callable[..., Any] | None = None,
    read_queue_summary_tool: Callable[..., Any] | None = None,
    search_grounding_tool: Callable[..., Any] | None = None,
) -> OperatorSupervisorAgent:
    return OperatorSupervisorAgent(
        read_dashboard_summary_tool=read_dashboard_summary_tool,
        read_queue_summary_tool=read_queue_summary_tool,
        search_grounding_tool=search_grounding_tool,
    )


def build_dispatch_collaboration_agent(
    *,
    read_queue_summary_tool: Callable[..., Any] | None = None,
    search_grounding_tool: Callable[..., Any] | None = None,
) -> DispatchCollaborationAgent:
    return DispatchCollaborationAgent(
        read_queue_summary_tool=read_queue_summary_tool,
        search_grounding_tool=search_grounding_tool,
    )


def _operator_recommended_actions(
    dashboard_summary: dict[str, Any],
    queue_summary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sla_risk = _int_value(dashboard_summary.get("sla_warning_count")) + _int_value(
        dashboard_summary.get("sla_breached_count")
    )
    escalated = _int_value(dashboard_summary.get("escalated_count"))
    top_queue = _select_top_queue(queue_summary)
    actions: list[dict[str, Any]] = []
    if sla_risk > 0:
        actions.append(
            {
                "action": "prioritize_sla_risk",
                "reason": f"SLA风险工单共 {sla_risk} 单，建议优先处理。",
                "risk": "sla_breach",
                "confidence": 0.82,
                "advice_only": True,
            }
        )
    if escalated > 0:
        actions.append(
            {
                "action": "focus_escalated_queue",
                "reason": f"升级工单 {escalated} 单，需要优先分配资深处理人。",
                "risk": "escalation_backlog",
                "confidence": 0.79,
                "advice_only": True,
            }
        )
    if top_queue:
        actions.append(
            {
                "action": "rebalance_queue",
                "reason": f"建议优先支援队列 {top_queue}。",
                "risk": "queue_overload",
                "confidence": 0.74,
                "advice_only": True,
            }
        )
    return actions[:4]


def _dispatch_recommended_actions(priorities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not priorities:
        return []
    actions: list[dict[str, Any]] = []
    for item in priorities[:3]:
        queue_name = str(item.get("queue_name") or "unknown")
        actions.append(
            {
                "action": "suggest_dispatch",
                "target_queue": queue_name,
                "reason": (
                    f"队列 {queue_name} 升级={_int_value(item.get('escalated_count'))}，"
                    f"违约={_int_value(item.get('breached_count'))}。"
                ),
                "requires_policy_gate": True,
                "advice_only": True,
                "confidence": 0.73,
            }
        )
    return actions


def _select_top_queue(queue_summary: list[dict[str, Any]]) -> str | None:
    if not queue_summary:
        return None
    ranked = sorted(
        queue_summary,
        key=lambda item: (
            _int_value(item.get("breached_count")),
            _int_value(item.get("warning_count")),
            _int_value(item.get("escalated_count")),
            _int_value(item.get("in_progress_count")),
        ),
        reverse=True,
    )
    top_queue = ranked[0].get("queue_name")
    if isinstance(top_queue, str) and top_queue:
        return top_queue
    return None


def _contains_terminal_action_request(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(hint in lowered for hint in DispatchCollaborationAgent._TERMINAL_HINTS)


def _runtime_trace(
    *,
    agent: str,
    mode: str,
    tool_calls: list[dict[str, Any]],
    policy_gate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "agent": agent,
        "mode": mode,
        "tool_calls": tool_calls,
        "policy_gate": policy_gate,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _confidence_score(*, grounding_count: int, recommendation_count: int) -> float:
    base = 0.52
    base += min(0.28, 0.07 * grounding_count)
    base += min(0.18, 0.06 * recommendation_count)
    return round(max(0.0, min(1.0, base)), 2)


def _int_value(raw: Any) -> int:
    if isinstance(raw, int):
        return raw
    try:
        return int(str(raw or "0"))
    except ValueError:
        return 0


def _safe_tool_call(tool: Callable[..., Any] | None, **kwargs: Any) -> Any:
    if tool is None:
        return None
    try:
        return tool(**kwargs)
    except Exception:
        return None
