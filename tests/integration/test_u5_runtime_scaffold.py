from __future__ import annotations

from pathlib import Path

import pytest

from runtime.checkpoints.store import FileCheckpointStore
from runtime.graph.scaffold import RuntimeScaffold


def test_u5_runtime_scaffold_runs_interrupts_and_resumes(tmp_path: Path) -> None:
    checkpoint_store = FileCheckpointStore(tmp_path / "u5_runtime_checkpoints.json")
    runtime = RuntimeScaffold(checkpoint_store=checkpoint_store)

    started = runtime.start(
        ticket_id="TCK-U5-001",
        session_id="session-u5-001",
        message_text="停车场闸机损坏，需要处理",
        actor_id="u_intake_01",
    )

    assert started.interrupted is True
    assert started.current_node == "approval_wait"
    assert started.checkpoint_id is not None
    assert started.state["approval"]["status"] == "pending_approval"
    for field in (
        "ticket",
        "session",
        "handoff",
        "approval",
        "grounding",
        "trace",
        "copilot_outputs",
        "channel_route",
    ):
        assert field in started.state
    assert "collab_target" in started.state["channel_route"]
    assert "dispatch_decision" in started.state["channel_route"]
    assert "delivery_status" in started.state["channel_route"]

    persisted = checkpoint_store.load(started.checkpoint_id)
    assert persisted["ticket"]["ticket_id"] == "TCK-U5-001"
    assert persisted["session"]["session_id"] == "session-u5-001"

    resumed = runtime.resume(
        checkpoint_id=started.checkpoint_id,
        decision="approve",
        actor_id="u_supervisor_01",
    )

    assert resumed.interrupted is False
    assert resumed.current_node == "resolve_candidate"
    assert resumed.checkpoint_id is None
    assert resumed.state["approval"]["status"] == "approved"
    assert resumed.state["ticket"]["status"] == "resolved_candidate"
    assert resumed.state["trace"][-1]["node"] == "resolve_candidate"

    with pytest.raises(KeyError):
        checkpoint_store.load(started.checkpoint_id)
