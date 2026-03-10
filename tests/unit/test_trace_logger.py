from __future__ import annotations

from pathlib import Path

from core.trace_logger import JsonTraceLogger, new_trace_id


def test_trace_logger_query_by_trace_ticket_session(tmp_path: Path) -> None:
    log_path = tmp_path / "trace.log"
    logger = JsonTraceLogger(log_path)

    trace_id = new_trace_id()
    logger.log(
        "route_decision", {"intent": "faq"}, trace_id=trace_id, ticket_id="T-1", session_id="S-1"
    )
    logger.log(
        "tool_call_end", {"tool": "search_kb"}, trace_id=trace_id, ticket_id="T-1", session_id="S-1"
    )
    logger.log(
        "other_trace", {"ok": True}, trace_id=new_trace_id(), ticket_id="T-2", session_id="S-2"
    )

    assert len(logger.query_by_trace(trace_id)) == 2
    assert len(logger.query_by_ticket("T-1")) == 2
    assert len(logger.query_by_session("S-1")) == 2
