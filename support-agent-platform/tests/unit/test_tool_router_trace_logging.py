from __future__ import annotations

from pathlib import Path

from core.retriever import Retriever
from core.ticket_api import TicketAPI
from core.tool_router import ToolRouter
from core.trace_logger import JsonTraceLogger
from openclaw_adapter.session_mapper import SessionMapper
from storage.ticket_repository import TicketRepository


def test_tool_router_writes_tool_trace_events(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    log_path = tmp_path / "trace.log"

    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    logger = JsonTraceLogger(log_path)

    ticket_api = TicketAPI(repo, session_mapper=SessionMapper(sqlite_path))
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    router = ToolRouter(ticket_api=ticket_api, retriever=retriever, trace_logger=logger)

    trace_id = "trace_tool_001"
    result = router.execute(
        "create_ticket",
        {
            "channel": "telegram",
            "session_id": "session-tool",
            "thread_id": "thread-tool",
            "title": "追踪测试",
            "latest_message": "设备故障",
            "intent": "repair",
            "trace_id": trace_id,
        },
    )

    assert str(result.output["ticket_id"]).startswith("TCK-")

    events = logger.query_by_trace(trace_id)
    event_types = [item["event_type"] for item in events]
    assert "tool_call_start" in event_types
    assert "tool_call_end" in event_types
