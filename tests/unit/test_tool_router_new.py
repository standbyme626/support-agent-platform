from __future__ import annotations

from pathlib import Path

from core.retriever import Retriever
from core.ticket_api import TicketAPI
from core.tool_router import ToolRouter
from openclaw_adapter.session_mapper import SessionMapper
from storage.ticket_repository import TicketRepository


def test_tool_router_dispatches_core_tools(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()

    ticket_api = TicketAPI(repo, session_mapper=SessionMapper(sqlite_path))
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    router = ToolRouter(ticket_api=ticket_api, retriever=retriever)

    created = router.execute(
        "create_ticket",
        {
            "channel": "wecom",
            "session_id": "s-2",
            "thread_id": "th-2",
            "title": "报修",
            "latest_message": "设备故障",
            "intent": "repair",
            "priority": "P2",
        },
    )
    ticket_id = str(created.output["ticket_id"])

    updated = router.execute(
        "update_ticket",
        {"ticket_id": ticket_id, "actor_id": "agent-1", "updates": {"queue": "repair"}},
    )
    assert updated.output["status"] == "open"

    escalated = router.execute(
        "escalate_case",
        {"ticket_id": ticket_id, "actor_id": "agent-1", "reason": "超时风险"},
    )
    assert escalated.output["status"] == "escalated"

    docs = router.execute("search_kb", {"source_type": "sop", "query": "报修 故障", "top_k": 1})
    assert docs.output
