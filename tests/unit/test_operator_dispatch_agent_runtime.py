from __future__ import annotations

from app.agents.deep.operator_dispatch_agent import (
    build_dispatch_collaboration_agent,
    build_operator_supervisor_agent,
)


def _dashboard_summary_with_sla_risk() -> dict[str, int]:
    return {
        "new_tickets_today": 12,
        "in_progress_count": 18,
        "handoff_pending_count": 4,
        "escalated_count": 3,
        "sla_warning_count": 5,
        "sla_breached_count": 2,
        "consulting_reuse_count": 0,
        "duplicate_candidates_count": 0,
        "merge_accept_count": 0,
        "merge_reject_count": 0,
        "merge_accept_rate": 0,
    }


def _queue_summary() -> list[dict[str, int | str]]:
    return [
        {
            "queue_name": "support",
            "open_count": 10,
            "in_progress_count": 12,
            "warning_count": 4,
            "breached_count": 1,
            "escalated_count": 2,
            "assignee_count": 3,
        },
        {
            "queue_name": "infra",
            "open_count": 2,
            "in_progress_count": 5,
            "warning_count": 0,
            "breached_count": 0,
            "escalated_count": 0,
            "assignee_count": 2,
        },
    ]


def test_operator_agent_highlights_queue_pressure() -> None:
    agent = build_operator_supervisor_agent(
        read_dashboard_summary_tool=_dashboard_summary_with_sla_risk,
        read_queue_summary_tool=_queue_summary,
        search_grounding_tool=lambda query: [{"source_id": "kb-ops-1"}],
    )

    result = agent.analyze("今天队列压力如何")

    assert result["scope"] == "operator"
    assert result["dashboard_summary"]["in_progress_count"] == 18
    assert result["recommended_actions"]
    assert result["runtime_trace"]["agent"] == "operator_supervisor_agent_v1"
    assert result["advice_only"] is True


def test_operator_agent_reports_sla_risk_recommendation() -> None:
    agent = build_operator_supervisor_agent(
        read_dashboard_summary_tool=_dashboard_summary_with_sla_risk,
        read_queue_summary_tool=_queue_summary,
        search_grounding_tool=lambda query: [{"source_id": "kb-ops-2"}],
    )

    result = agent.analyze("SLA风险怎么处理")

    assert result["scope"] == "operator"
    assert any("SLA" in str(action.get("reason", "")) for action in result["recommended_actions"])
    assert 0.0 <= float(result["confidence"]) <= 1.0


def test_dispatch_agent_returns_dispatch_priority_suggestions() -> None:
    agent = build_dispatch_collaboration_agent(
        read_queue_summary_tool=_queue_summary,
        search_grounding_tool=lambda query: [{"source_id": "kb-dsp-1"}],
    )

    result = agent.analyze("请给出调度建议")

    assert result["scope"] == "dispatch"
    assert isinstance(result["dispatch_priority"], list)
    assert result["dispatch_priority"][0]["queue_name"] == "support"
    assert result["recommended_actions"]
    assert result["advice_only"] is True


def test_dispatch_agent_blocks_terminal_execution_requests() -> None:
    agent = build_dispatch_collaboration_agent(
        read_queue_summary_tool=_queue_summary,
        search_grounding_tool=lambda query: [{"source_id": "kb-dsp-2"}],
    )

    result = agent.analyze("请直接执行 reassign 并关闭工单")

    assert result["scope"] == "dispatch"
    assert result["advice_only"] is True
    assert result["runtime_trace"]["policy_gate"]["enforced"] is True
    assert result["runtime_trace"]["policy_gate"]["blocked_execution"] is True
