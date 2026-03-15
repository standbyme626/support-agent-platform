from __future__ import annotations

from app.graph_runtime.collab_graph import build_collab_graph


def test_collab_graph_requires_approval_and_supports_resume() -> None:
    graph = build_collab_graph()
    started = graph.run(
        ticket_id="TICKET-U5-COLLAB-001",
        action="operator_close",
        actor_id="u_ops_01",
        note="manual close requested",
    )

    assert started["requires_approval"] is True
    assert started["approval_status"] == "pending_approval"
    assert started["interrupted"] is True
    assert isinstance(started.get("pause_checkpoint_id"), str)
    checkpoint_id = str(started["pause_checkpoint_id"])

    approved = graph.resume(
        checkpoint_id=checkpoint_id,
        decision="approve",
        actor_id="u_supervisor_01",
    )
    assert approved["approval_status"] == "approved"
    assert approved["result_action"] == "operator_close"
    assert approved["interrupted"] is False
    assert approved["pause_checkpoint_id"] is None


def test_collab_graph_reject_resume_blocks_terminal_action() -> None:
    graph = build_collab_graph()
    started = graph.run(
        ticket_id="TICKET-U5-COLLAB-002",
        action="resolve",
        actor_id="u_ops_02",
    )
    checkpoint_id = str(started["pause_checkpoint_id"])

    rejected = graph.resume(
        checkpoint_id=checkpoint_id,
        decision="reject",
        actor_id="u_supervisor_02",
    )
    assert rejected["approval_status"] == "rejected"
    assert rejected["result_action"] == "rejected"
    assert rejected["interrupted"] is False


def test_collab_graph_non_terminal_action_executes_without_interrupt() -> None:
    graph = build_collab_graph()
    started = graph.run(
        ticket_id="TICKET-U5-COLLAB-003",
        action="claim",
        actor_id="u_ops_03",
    )

    assert started["requires_approval"] is False
    assert started["approval_status"] == "not_required"
    assert started["result_action"] == "claim"
    assert started["interrupted"] is False
    assert started["pause_checkpoint_id"] is None
