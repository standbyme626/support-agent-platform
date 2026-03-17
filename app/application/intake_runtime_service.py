from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from app.agents.deep.ticket_investigation_agent import run_ticket_investigation
from core.disambiguation import detect_session_control
from core.trace_logger import new_trace_id


def extract_runtime_trace_fields(
    result_payload: dict[str, Any],
    *,
    default_graph: str,
) -> tuple[str, str, list[str], dict[str, Any]]:
    trace_payload = result_payload.get("trace")
    trace_details = trace_payload if isinstance(trace_payload, dict) else {}
    runtime_graph = str(trace_details.get("graph") or default_graph)
    steps_payload = trace_details.get("steps")
    runtime_path: list[str] = []
    if isinstance(steps_payload, list):
        for item in steps_payload:
            if not isinstance(item, dict):
                continue
            step_name = str(item.get("step") or "").strip()
            if step_name:
                runtime_path.append(step_name)

    runtime_current_node = runtime_path[-1] if runtime_path else "unknown"
    decision_payload = result_payload.get("decision")
    decision = decision_payload if isinstance(decision_payload, dict) else {}
    runtime_state: dict[str, Any] = {
        "route": decision.get("route"),
        "high_risk_action_executed": bool(decision.get("high_risk_action_executed", False)),
    }
    session_action_payload = result_payload.get("session_action")
    if isinstance(session_action_payload, dict):
        session_action = str(session_action_payload.get("action") or "").strip()
        if session_action:
            runtime_state["session_action"] = session_action
    intake_result_payload = result_payload.get("intake_result")
    if isinstance(intake_result_payload, dict):
        runtime_state["intake_status"] = intake_result_payload.get("status")
    return runtime_graph, runtime_current_node, runtime_path, runtime_state


def run_intake_graph_v2(
    runtime: Any,
    *,
    payload: dict[str, Any],
    run_session_end_v2: Callable[..., dict[str, Any]],
    run_session_new_issue: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    metadata_payload = payload.get("metadata")
    metadata = dict(metadata_payload) if isinstance(metadata_payload, dict) else {}
    session_id = str(payload.get("session_id") or metadata.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    text = str(
        payload.get("text") or payload.get("message_text") or payload.get("query") or ""
    ).strip()
    if not text:
        raise ValueError("text is required")
    actor_id = (
        str(payload.get("actor_id") or metadata.get("actor_id") or "ops-api").strip() or "ops-api"
    )
    metadata.setdefault("actor_id", actor_id)
    if payload.get("ticket_id"):
        metadata.setdefault("ticket_id", str(payload.get("ticket_id")))

    previous_payload = payload.get("previous")
    previous = previous_payload if isinstance(previous_payload, dict) else None
    trace_id = str(payload.get("trace_id") or new_trace_id()).strip()
    session_control = detect_session_control(text)
    if session_control is not None and session_control.action in {"session_end", "new_issue"}:
        if session_control.action == "session_end":
            action_result = run_session_end_v2(
                runtime,
                session_id=session_id,
                payload={
                    "actor_id": actor_id,
                    "reason": "user_requested_end",
                    "trace_id": trace_id,
                },
            )
        else:
            action_result = run_session_new_issue(
                runtime,
                session_id=session_id,
                payload={
                    "actor_id": actor_id,
                    "reason": "user_requested_new_issue",
                    "trace_id": trace_id,
                },
            )
        control_result = {
            "session_id": session_id,
            "user_id": str(payload.get("user_id") or ""),
            "channel": str(payload.get("channel") or "ops-api"),
            "intent": "session_control",
            "decision": {
                "route": session_control.action,
                "high_risk_action_executed": False,
            },
            "intake_result": {
                "status": "skipped",
                "reason": f"session_control_{session_control.action}",
            },
            "investigation": None,
            "session_action": {
                "action": session_control.action,
                "reason": session_control.reason,
                "source": session_control.source,
                "priority": session_control.priority,
                "result": action_result,
            },
            "trace": {
                "graph": "intake_graph_v1",
                "previous_checkpoint": previous,
                "steps": [
                    {
                        "step": "input_received",
                        "details": {"session_id": session_id},
                        "at": datetime.now(UTC).isoformat(),
                    },
                    {
                        "step": "session_control_routed",
                        "details": {
                            "action": session_control.action,
                            "reason": session_control.reason,
                            "source": session_control.source,
                        },
                        "at": datetime.now(UTC).isoformat(),
                    },
                ],
            },
        }
        runtime.trace_logger.log(
            "intake_run_v2",
            {
                "session_id": session_id,
                "intent": control_result.get("intent"),
                "route": session_control.action,
                "advice_only": True,
                "high_risk_action_executed": False,
                "session_action": session_control.action,
                "session_action_reason": session_control.reason,
            },
            trace_id=trace_id,
            ticket_id=str(metadata.get("ticket_id") or "").strip() or None,
            session_id=session_id,
        )
        runtime_graph, runtime_current_node, runtime_path, runtime_state = extract_runtime_trace_fields(
            control_result,
            default_graph="intake_graph_v1",
        )
        return {
            "result": control_result,
            "advice_only": True,
            "high_risk_action_executed": False,
            "runtime_graph": runtime_graph,
            "runtime_current_node": runtime_current_node,
            "runtime_path": runtime_path,
            "runtime_state": runtime_state,
            "trace": {
                "trace_id": trace_id,
                "graph": runtime_graph,
            },
        }

    result = runtime.intake_graph_runner(
        {
            "session_id": session_id,
            "user_id": str(payload.get("user_id") or ""),
            "text": text,
            "channel": str(payload.get("channel") or "ops-api"),
            "metadata": metadata,
        },
        previous=previous,
    )
    if not isinstance(result, dict):
        raise ValueError("intake graph returned invalid result")

    decision_payload = result.get("decision")
    decision = decision_payload if isinstance(decision_payload, dict) else {}
    investigation_payload = result.get("investigation")
    investigation = investigation_payload if isinstance(investigation_payload, dict) else {}
    safety_payload = investigation.get("safety")
    safety = safety_payload if isinstance(safety_payload, dict) else {}
    advice_only = bool(safety.get("advice_only", True))
    high_risk_action_executed = bool(decision.get("high_risk_action_executed", False))
    runtime.trace_logger.log(
        "intake_run_v2",
        {
            "session_id": session_id,
            "intent": result.get("intent"),
            "route": decision.get("route"),
            "advice_only": advice_only,
            "high_risk_action_executed": high_risk_action_executed,
        },
        trace_id=trace_id,
        ticket_id=str(metadata.get("ticket_id") or "").strip() or None,
        session_id=session_id,
    )
    runtime_graph, runtime_current_node, runtime_path, runtime_state = extract_runtime_trace_fields(
        result,
        default_graph="intake_graph_v1",
    )
    return {
        "result": result,
        "advice_only": advice_only,
        "high_risk_action_executed": high_risk_action_executed,
        "runtime_graph": runtime_graph,
        "runtime_current_node": runtime_current_node,
        "runtime_path": runtime_path,
        "runtime_state": runtime_state,
        "trace": {
            "trace_id": trace_id,
            "graph": runtime_graph,
        },
    }


def run_ticket_investigation_v2(
    runtime: Any,
    *,
    ticket_id: str,
    payload: dict[str, Any],
    ticket_trace_id_getter: Callable[[Any], str | None],
) -> dict[str, Any]:
    ticket = runtime.ticket_api.require_ticket(ticket_id)
    actor_id = str(payload.get("actor_id") or "ops-api").strip() or "ops-api"
    question = str(
        payload.get("question")
        or payload.get("query")
        or ticket.latest_message
        or "Please investigate this ticket."
    ).strip()
    if not question:
        raise ValueError("question is required")
    trace_id = str(payload.get("trace_id") or ticket_trace_id_getter(ticket) or new_trace_id()).strip()
    investigation = run_ticket_investigation(
        runtime.investigation_agent,
        ticket_id=ticket_id,
        actor=actor_id,
        question=question,
    )
    safety_payload = investigation.get("safety")
    safety = safety_payload if isinstance(safety_payload, dict) else {}
    advice_only = bool(safety.get("advice_only", False))
    if not advice_only:
        safety = {
            **safety,
            "advice_only": True,
            "high_risk_actions_executed": [],
            "requires_hitl_for_terminal_actions": True,
        }
        investigation["safety"] = safety
        advice_only = True
    high_risk_actions_payload = safety.get("high_risk_actions_executed")
    high_risk_actions = high_risk_actions_payload if isinstance(high_risk_actions_payload, list) else []
    runtime.trace_logger.log(
        "ticket_investigation_v2",
        {
            "ticket_id": ticket_id,
            "actor_id": actor_id,
            "question": question,
            "advice_only": advice_only,
            "high_risk_actions_executed": list(high_risk_actions),
        },
        trace_id=trace_id,
        ticket_id=ticket_id,
        session_id=ticket.session_id,
    )
    trace_payload = investigation.get("trace")
    trace_details = trace_payload if isinstance(trace_payload, dict) else {}
    return {
        "ticket_id": ticket_id,
        "session_id": ticket.session_id,
        "question": question,
        "investigation": investigation,
        "advice_only": advice_only,
        "trace": {
            "trace_id": trace_id,
            "agent": str(trace_details.get("agent") or "ticket_investigation_agent_v1"),
        },
    }
