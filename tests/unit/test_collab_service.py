from __future__ import annotations

from app.application.collab_service import CollabService


def test_collab_service_prepare_and_resume_approval_action() -> None:
    service = CollabService()

    prepared = service.prepare_action(
        ticket_id="TICKET-COLLAB-SVC-001",
        action="operator-close",
        actor_id="u_ops_01",
        note="manual close requested",
    )
    assert prepared["normalized_action"] == "operator_close"
    assert prepared["requires_approval"] is True
    checkpoint_id = str(prepared["pause_checkpoint_id"])
    assert checkpoint_id

    resumed = service.resume_action(
        checkpoint_id=checkpoint_id,
        decision="approve",
        actor_id="u_supervisor_01",
    )
    assert resumed["approval_status"] == "approved"
    assert resumed["result_action"] == "operator_close"


def test_collab_service_maps_close_alias_to_customer_confirm() -> None:
    service = CollabService()
    prepared = service.prepare_action(
        ticket_id="TICKET-COLLAB-SVC-002",
        action="close",
        actor_id="u_ops_02",
        note="compat close alias",
    )
    assert prepared["normalized_action"] == "customer_confirm"
