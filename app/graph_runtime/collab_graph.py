from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

ApprovalDecision = Literal["approve", "reject"]


class CollabGraphState(TypedDict, total=False):
    ticket_id: str
    action: str
    actor_id: str
    note: str
    metadata: dict[str, Any]
    trace: list[dict[str, Any]]
    requires_approval: bool
    approval_status: str
    interrupted: bool
    pause_checkpoint_id: str | None
    decision: ApprovalDecision | None
    decided_by: str | None
    result_action: str | None


class CollabGraphRuntime:
    """Minimal collaboration graph runtime with checkpoint-based approval resume."""

    def __init__(self, *, checkpoints: dict[str, CollabGraphState] | None = None) -> None:
        self._checkpoints = checkpoints if checkpoints is not None else {}
        self._pre_approval_graph = _build_pre_approval_graph()
        self._resume_graph = _build_resume_graph()

    def run(
        self,
        *,
        ticket_id: str,
        action: str,
        actor_id: str,
        note: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CollabGraphState:
        initial: CollabGraphState = {
            "ticket_id": ticket_id,
            "action": action,
            "actor_id": actor_id,
            "note": note,
            "metadata": dict(metadata or {}),
            "trace": [],
            "requires_approval": False,
            "approval_status": "not_required",
            "interrupted": False,
            "pause_checkpoint_id": None,
            "decision": None,
            "decided_by": None,
            "result_action": None,
        }
        state = self._pre_approval_graph.invoke(initial)
        if bool(state.get("interrupted")):
            checkpoint_id = f"cp-{uuid4().hex}"
            state["pause_checkpoint_id"] = checkpoint_id
            self._checkpoints[checkpoint_id] = _clone_state(state)
        return state

    def resume(
        self,
        *,
        checkpoint_id: str,
        decision: ApprovalDecision,
        actor_id: str,
    ) -> CollabGraphState:
        if checkpoint_id not in self._checkpoints:
            raise KeyError(f"checkpoint {checkpoint_id} not found")
        state = _clone_state(self._checkpoints[checkpoint_id])
        state["decision"] = decision
        state["decided_by"] = actor_id
        state["interrupted"] = False
        resumed = self._resume_graph.invoke(state)
        resumed["pause_checkpoint_id"] = None
        self._checkpoints.pop(checkpoint_id, None)
        return resumed


def build_collab_graph(
    *,
    checkpoints: dict[str, CollabGraphState] | None = None,
) -> CollabGraphRuntime:
    return CollabGraphRuntime(checkpoints=checkpoints)


def _build_pre_approval_graph() -> Any:
    builder = StateGraph(CollabGraphState)
    builder.add_node("prepare_action", _prepare_action_node)
    builder.add_node("approval_wait", _approval_wait_node)
    builder.add_node("execute_action", _execute_action_node)
    builder.add_edge(START, "prepare_action")
    builder.add_conditional_edges(
        "prepare_action",
        _route_after_prepare,
        {"approval_wait": "approval_wait", "execute_action": "execute_action"},
    )
    builder.add_edge("approval_wait", END)
    builder.add_edge("execute_action", END)
    return builder.compile()


def _build_resume_graph() -> Any:
    builder = StateGraph(CollabGraphState)
    builder.add_node("resume_decision", _resume_decision_node)
    builder.add_node("execute_action", _execute_action_node)
    builder.add_node("reject_action", _reject_action_node)
    builder.add_edge(START, "resume_decision")
    builder.add_conditional_edges(
        "resume_decision",
        _route_after_resume,
        {"execute_action": "execute_action", "reject_action": "reject_action"},
    )
    builder.add_edge("execute_action", END)
    builder.add_edge("reject_action", END)
    return builder.compile()


def _prepare_action_node(state: CollabGraphState) -> CollabGraphState:
    next_state = _clone_state(state)
    action = str(next_state.get("action") or "")
    requires_approval = action in {
        "resolve",
        "customer_confirm",
        "operator_close",
        "reassign",
        "escalate",
    }
    next_state["requires_approval"] = requires_approval
    next_state["approval_status"] = "pending_approval" if requires_approval else "not_required"
    _append_trace(
        next_state,
        node="prepare_action",
        event="collab_action_prepared",
        detail={"action": action, "requires_approval": requires_approval},
    )
    return next_state


def _approval_wait_node(state: CollabGraphState) -> CollabGraphState:
    next_state = _clone_state(state)
    next_state["interrupted"] = True
    next_state["result_action"] = None
    _append_trace(
        next_state,
        node="approval_wait",
        event="collab_approval_wait",
        detail={"approval_status": "pending_approval"},
    )
    return next_state


def _execute_action_node(state: CollabGraphState) -> CollabGraphState:
    next_state = _clone_state(state)
    action = str(next_state.get("action") or "")
    if next_state.get("decision") == "approve":
        next_state["approval_status"] = "approved"
    next_state["result_action"] = action
    next_state["interrupted"] = False
    _append_trace(
        next_state,
        node="execute_action",
        event="collab_action_executed",
        detail={"result_action": action},
    )
    return next_state


def _resume_decision_node(state: CollabGraphState) -> CollabGraphState:
    next_state = _clone_state(state)
    decision = str(next_state.get("decision") or "")
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    next_state["approval_status"] = "approved" if decision == "approve" else "rejected"
    _append_trace(
        next_state,
        node="resume_decision",
        event="collab_approval_resumed",
        actor_id=str(next_state.get("decided_by") or ""),
        detail={"decision": decision},
    )
    return next_state


def _reject_action_node(state: CollabGraphState) -> CollabGraphState:
    next_state = _clone_state(state)
    next_state["result_action"] = "rejected"
    next_state["interrupted"] = False
    _append_trace(
        next_state,
        node="reject_action",
        event="collab_action_rejected",
        detail={"action": str(next_state.get("action") or "")},
    )
    return next_state


def _route_after_prepare(state: CollabGraphState) -> str:
    return "approval_wait" if bool(state.get("requires_approval")) else "execute_action"


def _route_after_resume(state: CollabGraphState) -> str:
    return "execute_action" if state.get("decision") == "approve" else "reject_action"


def _append_trace(
    state: CollabGraphState,
    *,
    node: str,
    event: str,
    actor_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    trace = list(state.get("trace") or [])
    row: dict[str, Any] = {
        "node": node,
        "event": event,
        "at": datetime.now(UTC).isoformat(),
    }
    if actor_id:
        row["actor_id"] = actor_id
    if detail:
        row["detail"] = detail
    trace.append(row)
    state["trace"] = trace


def _clone_state(state: CollabGraphState) -> CollabGraphState:
    return copy.deepcopy(state)
