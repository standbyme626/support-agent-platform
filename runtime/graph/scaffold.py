from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from runtime.checkpoints import CheckpointStoreProtocol, FileCheckpointStore
from runtime.state import (
    RuntimeState,
    append_trace_entry,
    build_initial_runtime_state,
    clone_runtime_state,
)

ResumeDecision = Literal["approve", "reject"]


@dataclass(frozen=True)
class RuntimeRunResult:
    state: RuntimeState
    current_node: str
    interrupted: bool
    checkpoint_id: str | None


class RuntimeScaffold:
    """Minimal Upgrade 5 runtime with graph execution + checkpoint resume."""

    def __init__(self, *, checkpoint_store: CheckpointStoreProtocol) -> None:
        self._checkpoint_store = checkpoint_store
        self._pre_approval_graph = _build_pre_approval_graph()
        self._resume_graph = _build_resume_graph()

    @classmethod
    def with_file_checkpoint(cls, checkpoint_path: Path) -> RuntimeScaffold:
        return cls(checkpoint_store=FileCheckpointStore(checkpoint_path))

    def start(
        self,
        *,
        ticket_id: str,
        session_id: str,
        message_text: str,
        actor_id: str,
    ) -> RuntimeRunResult:
        state = build_initial_runtime_state(
            ticket_id=ticket_id,
            session_id=session_id,
            message_text=message_text,
            actor_id=actor_id,
        )
        pre_approval_state = self._pre_approval_graph.invoke(state)
        checkpoint_id = self._checkpoint_store.save(pre_approval_state, next_node="resume")
        result_state = clone_runtime_state(pre_approval_state)
        result_state["runtime"]["interrupted"] = True
        result_state["runtime"]["checkpoint_id"] = checkpoint_id
        return RuntimeRunResult(
            state=result_state,
            current_node="approval_wait",
            interrupted=True,
            checkpoint_id=checkpoint_id,
        )

    def resume(
        self,
        *,
        checkpoint_id: str,
        decision: ResumeDecision,
        actor_id: str,
    ) -> RuntimeRunResult:
        record = self._checkpoint_store.load_record(checkpoint_id)
        if record.next_node != "resume":
            raise RuntimeError(
                f"checkpoint {checkpoint_id} expected next_node='resume', got {record.next_node!r}"
            )
        state = clone_runtime_state(record.state)
        state["approval"]["decision"] = decision
        state["approval"]["decided_by"] = actor_id
        resumed_state = self._resume_graph.invoke(state)
        self._checkpoint_store.delete(checkpoint_id)
        resumed_state["runtime"]["checkpoint_id"] = None
        resumed_state["runtime"]["interrupted"] = False
        return RuntimeRunResult(
            state=resumed_state,
            current_node=str(resumed_state["runtime"]["current_node"]),
            interrupted=False,
            checkpoint_id=None,
        )


def _build_pre_approval_graph() -> Any:
    builder = StateGraph(RuntimeState)
    builder.add_node("ticket_open", _ticket_open_node)
    builder.add_node("investigate", _investigate_node)
    builder.add_node("approval_wait", _approval_wait_node)
    builder.add_edge(START, "ticket_open")
    builder.add_edge("ticket_open", "investigate")
    builder.add_edge("investigate", "approval_wait")
    builder.add_edge("approval_wait", END)
    return builder.compile()


def _build_resume_graph() -> Any:
    builder = StateGraph(RuntimeState)
    builder.add_node("resume", _resume_node)
    builder.add_node("resolve_candidate", _resolve_candidate_node)
    builder.add_edge(START, "resume")
    builder.add_edge("resume", "resolve_candidate")
    builder.add_edge("resolve_candidate", END)
    return builder.compile()


def _ticket_open_node(state: RuntimeState) -> RuntimeState:
    next_state = clone_runtime_state(state)
    next_state["ticket"]["status"] = "open"
    next_state["runtime"]["current_node"] = "ticket_open"
    append_trace_entry(
        next_state,
        node="ticket_open",
        event="ticket_opened",
        actor_id=str(next_state["session"]["actor_id"]),
    )
    return next_state


def _investigate_node(state: RuntimeState) -> RuntimeState:
    next_state = clone_runtime_state(state)
    next_state["runtime"]["current_node"] = "investigate"
    next_state["grounding"]["sources"] = [
        {
            "type": "kb_doc",
            "doc_id": "kb-u5-runtime-scaffold",
            "score": 0.74,
        }
    ]
    next_state["copilot_outputs"]["ticket"] = {
        "answer": "建议先确认故障范围并通知值班处理人。",
        "recommended_actions": ["collect-photo-evidence", "notify-oncall"],
        "confidence": 0.74,
    }
    append_trace_entry(
        next_state,
        node="investigate",
        event="ticket_investigated",
        detail={"grounding_count": len(next_state["grounding"]["sources"])},
    )
    return next_state


def _approval_wait_node(state: RuntimeState) -> RuntimeState:
    next_state = clone_runtime_state(state)
    next_state["runtime"]["current_node"] = "approval_wait"
    next_state["approval"]["status"] = "pending_approval"
    append_trace_entry(
        next_state,
        node="approval_wait",
        event="approval_requested",
        detail={"approval_id": next_state["approval"]["approval_id"]},
    )
    return next_state


def _resume_node(state: RuntimeState) -> RuntimeState:
    next_state = clone_runtime_state(state)
    decision = str(next_state["approval"].get("decision") or "")
    next_state["runtime"]["current_node"] = "resume"
    next_state["approval"]["status"] = "approved" if decision == "approve" else "rejected"
    append_trace_entry(
        next_state,
        node="resume",
        event="approval_resumed",
        actor_id=str(next_state["approval"].get("decided_by") or ""),
        detail={"decision": decision},
    )
    return next_state


def _resolve_candidate_node(state: RuntimeState) -> RuntimeState:
    next_state = clone_runtime_state(state)
    next_state["runtime"]["current_node"] = "resolve_candidate"
    decision = str(next_state["approval"].get("decision") or "")
    next_state["ticket"]["status"] = (
        "resolved_candidate" if decision == "approve" else "needs_manual_followup"
    )
    append_trace_entry(
        next_state,
        node="resolve_candidate",
        event="resolve_candidate_generated",
        detail={"ticket_status": next_state["ticket"]["status"]},
    )
    return next_state
