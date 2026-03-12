from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:16]}"


class JsonTraceLogger:
    """Append-only JSONL logger for gateway/workflow traces."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._log_path

    def log(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        trace_id: str | None = None,
        ticket_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": trace_id,
            "ticket_id": ticket_id,
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload,
        }
        with self._log_path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        records = self._load_all()
        return records[-limit:]

    def query_by_trace(self, trace_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        events = [item for item in self._load_all() if item.get("trace_id") == trace_id]
        return events[-limit:]

    def query_by_ticket(self, ticket_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        events = [item for item in self._load_all() if item.get("ticket_id") == ticket_id]
        return events[-limit:]

    def latest_by_ticket(
        self, ticket_id: str, *, event_type: str | None = None
    ) -> dict[str, Any] | None:
        events = self.query_by_ticket(ticket_id, limit=2000)
        if event_type is None:
            return events[-1] if events else None
        for item in reversed(events):
            if str(item.get("event_type") or "") == event_type:
                return item
        return None

    def query_by_session(self, session_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        events = [item for item in self._load_all() if item.get("session_id") == session_id]
        return events[-limit:]

    def _load_all(self) -> list[dict[str, Any]]:
        if not self._log_path.exists():
            return []
        lines = self._log_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
