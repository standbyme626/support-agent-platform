from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from storage.models import SessionBinding


class SessionMapper:
    """Persist session bindings and metadata for stable context recovery."""

    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def get_or_create(
        self, session_id: str, metadata: dict[str, Any] | None = None
    ) -> SessionBinding:
        existing = self.get(session_id)
        if existing:
            merged_metadata = self._merge_metadata(existing.metadata, metadata)
            if merged_metadata != existing.metadata:
                self._upsert(
                    session_id=session_id,
                    thread_id=existing.thread_id,
                    ticket_id=existing.ticket_id,
                    metadata=merged_metadata,
                )
                return self.get(session_id) or existing
            return existing

        thread_id = self._build_thread_id(session_id)
        self._upsert(
            session_id=session_id,
            thread_id=thread_id,
            ticket_id=None,
            metadata=metadata or {},
        )
        created = self.get(session_id)
        if created is None:
            raise RuntimeError(f"Failed to create session binding for '{session_id}'")
        return created

    def set_ticket_id(
        self,
        session_id: str,
        ticket_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionBinding:
        binding = self.get_or_create(session_id, metadata=metadata)
        merged_metadata = self._merge_metadata(binding.metadata, metadata)
        self._upsert(
            session_id=session_id,
            thread_id=binding.thread_id,
            ticket_id=ticket_id,
            metadata=merged_metadata,
        )
        updated = self.get(session_id)
        if updated is None:
            raise RuntimeError(f"Failed to update session binding for '{session_id}'")
        return updated

    def get(self, session_id: str) -> SessionBinding | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_id, thread_id, ticket_id, metadata_json, updated_at
                FROM session_bindings
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            return None

        return SessionBinding(
            session_id=row["session_id"],
            thread_id=row["thread_id"],
            ticket_id=row["ticket_id"],
            metadata=json.loads(row["metadata_json"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM session_bindings").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def _initialize_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_bindings (
                    session_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    ticket_id TEXT,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _upsert(
        self,
        *,
        session_id: str,
        thread_id: str,
        ticket_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_bindings(
                    session_id, thread_id, ticket_id, metadata_json, updated_at
                )
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET
                  thread_id = excluded.thread_id,
                  ticket_id = excluded.ticket_id,
                  metadata_json = excluded.metadata_json,
                  updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    thread_id,
                    ticket_id,
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

    def _build_thread_id(self, session_id: str) -> str:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"support-agent-platform/{session_id}").hex

    @staticmethod
    def _merge_metadata(
        original: dict[str, Any] | None,
        incoming: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(original or {})
        if incoming:
            merged.update(incoming)
        return merged
