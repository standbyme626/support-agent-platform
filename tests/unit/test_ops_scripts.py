from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from core.trace_logger import JsonTraceLogger
from scripts.healthcheck import run_healthcheck
from scripts.replay_gateway_event import replay_event
from scripts.trace_debug import debug_trace


def test_healthcheck_and_trace_debug_scripts(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "ops.db"))

    health = run_healthcheck("dev")
    assert health["status"] in {"ok", "degraded"}

    log_path = Path(__file__).resolve().parents[2] / "storage" / "gateway-dev.log"
    logger = JsonTraceLogger(log_path)
    logger.log("script_test", {"ok": True}, trace_id="trace_ops_1", session_id="sess-ops")

    events = debug_trace(
        environment="dev",
        trace_id="trace_ops_1",
        ticket_id=None,
        session_id=None,
        limit=10,
    )
    assert any(event["event_type"] == "script_test" for event in events)

    replay_result = replay_event(
        environment="dev",
        channel="telegram",
        session_id="ops-session",
        text="hello from replay",
        trace_id="trace_ops_replay",
    )
    assert replay_result["status"] == "ok"
