from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from storage.models import SessionBinding

_SESSION_CONTEXT_KEY = "session_context"
_DEFAULT_RECENT_LIMIT = 5


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
        merged_metadata = self._bind_ticket_context(
            merged_metadata,
            ticket_id=ticket_id,
            fallback_active=binding.ticket_id,
        )
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

    def switch_active_ticket(
        self,
        session_id: str,
        ticket_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> SessionBinding:
        return self.set_ticket_id(session_id, ticket_id, metadata=metadata)

    def reset_session_context(
        self,
        session_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        keep_recent: bool = True,
        recent_limit: int = _DEFAULT_RECENT_LIMIT,
    ) -> SessionBinding:
        binding = self.get_or_create(session_id, metadata=metadata)
        merged_metadata = self._merge_metadata(binding.metadata, metadata)
        context = self._normalize_session_context(
            merged_metadata.get(_SESSION_CONTEXT_KEY),
            fallback_ticket_id=binding.ticket_id,
        )
        recent_ticket_ids = [
            str(item) for item in context["recent_ticket_ids"] if str(item).strip()
        ]
        active_ticket_id = str(context["active_ticket_id"] or "").strip() or None
        if keep_recent and active_ticket_id:
            recent_ticket_ids.insert(0, active_ticket_id)
        context["active_ticket_id"] = None
        context["recent_ticket_ids"] = self._dedupe_ticket_ids(
            recent_ticket_ids,
            limit=recent_limit,
        )
        context["session_mode"] = "awaiting_new_issue"
        context["updated_at"] = datetime.now(UTC).isoformat()
        merged_metadata[_SESSION_CONTEXT_KEY] = context
        self._upsert(
            session_id=session_id,
            thread_id=binding.thread_id,
            ticket_id=None,
            metadata=merged_metadata,
        )
        updated = self.get(session_id)
        if updated is None:
            raise RuntimeError(f"Failed to reset session context for '{session_id}'")
        return updated

    def begin_new_issue(
        self,
        session_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> SessionBinding:
        return self.reset_session_context(session_id, metadata=metadata, keep_recent=True)

    def get_session_context(self, session_id: str) -> dict[str, Any]:
        binding = self.get(session_id)
        if binding is None:
            return self._normalize_session_context(None)
        return self._normalize_session_context(
            binding.metadata.get(_SESSION_CONTEXT_KEY),
            fallback_ticket_id=binding.ticket_id,
        )

    def list_session_ticket_ids(
        self,
        session_id: str,
        *,
        include_active: bool = True,
        include_recent: bool = True,
        limit: int = _DEFAULT_RECENT_LIMIT + 1,
    ) -> list[str]:
        binding = self.get(session_id)
        if binding is None:
            return []
        context = self._normalize_session_context(
            binding.metadata.get(_SESSION_CONTEXT_KEY),
            fallback_ticket_id=binding.ticket_id,
        )
        ticket_ids: list[str] = []
        if include_active:
            active_ticket_id = str(context.get("active_ticket_id") or "").strip()
            if active_ticket_id:
                ticket_ids.append(active_ticket_id)
        if include_recent:
            ticket_ids.extend(
                [
                    str(item).strip()
                    for item in context.get("recent_ticket_ids", [])
                    if str(item).strip()
                ]
            )
        if binding.ticket_id:
            fallback_ticket_id = str(binding.ticket_id).strip()
            if fallback_ticket_id:
                ticket_ids.append(fallback_ticket_id)
        return self._dedupe_ticket_ids(ticket_ids, limit=limit)

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

    def list_bindings(self, *, limit: int = 200, offset: int = 0) -> list[SessionBinding]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, thread_id, ticket_id, metadata_json, updated_at
                FROM session_bindings
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            SessionBinding(
                session_id=str(row["session_id"]),
                thread_id=str(row["thread_id"]),
                ticket_id=(str(row["ticket_id"]) if row["ticket_id"] else None),
                metadata=json.loads(str(row["metadata_json"])),
                updated_at=datetime.fromisoformat(str(row["updated_at"])),
            )
            for row in rows
        ]

    def list_replay_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for binding in self.list_bindings(limit=500):
            raw_items = binding.metadata.get("replay_events")
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                events.append(
                    {
                        "session_id": binding.session_id,
                        "ticket_id": binding.ticket_id,
                        "thread_id": binding.thread_id,
                        "timestamp": str(item.get("timestamp") or ""),
                        "channel": item.get("channel"),
                        "idempotency_key": item.get("idempotency_key"),
                        "trace_id": item.get("trace_id"),
                    }
                )
        events.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return events[:limit]

    def record_idempotency_key(
        self,
        *,
        session_id: str,
        idempotency_key: str,
        trace_id: str | None,
        channel: str | None,
        history_limit: int = 50,
    ) -> tuple[bool, SessionBinding]:
        binding = self.get_or_create(session_id, metadata={"channel": channel} if channel else None)
        processed_message_ids = [
            str(item)
            for item in binding.metadata.get("processed_message_ids", [])
            if str(item).strip()
        ]
        is_duplicate = idempotency_key in processed_message_ids

        metadata_updates: dict[str, Any] = {
            "last_message_id": idempotency_key,
            "last_trace_id": trace_id,
        }
        if not is_duplicate:
            processed_message_ids.append(idempotency_key)
            metadata_updates["processed_message_ids"] = processed_message_ids[-history_limit:]
        else:
            replay_events = [
                dict(item)
                for item in binding.metadata.get("replay_events", [])
                if isinstance(item, dict)
            ]
            replay_events.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "channel": channel,
                    "idempotency_key": idempotency_key,
                    "trace_id": trace_id,
                }
            )
            metadata_updates["replay_count"] = int(binding.metadata.get("replay_count", 0)) + 1
            metadata_updates["last_replay_at"] = replay_events[-1]["timestamp"]
            metadata_updates["replay_events"] = replay_events[-history_limit:]

        updated = self.get_or_create(session_id, metadata=metadata_updates)
        return (not is_duplicate, updated)

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
            for key, value in incoming.items():
                if key != _SESSION_CONTEXT_KEY:
                    merged[key] = value
                    continue
                if not isinstance(value, dict):
                    merged[key] = value
                    continue
                previous = merged.get(_SESSION_CONTEXT_KEY)
                if isinstance(previous, dict):
                    nested = dict(previous)
                    nested.update(value)
                    merged[_SESSION_CONTEXT_KEY] = nested
                else:
                    merged[_SESSION_CONTEXT_KEY] = dict(value)
        return merged

    @classmethod
    def _bind_ticket_context(
        cls,
        metadata: dict[str, Any],
        *,
        ticket_id: str,
        fallback_active: str | None,
    ) -> dict[str, Any]:
        normalized_ticket_id = str(ticket_id).strip()
        if not normalized_ticket_id:
            return dict(metadata)
        context = cls._normalize_session_context(
            metadata.get(_SESSION_CONTEXT_KEY),
            fallback_ticket_id=fallback_active,
        )
        active_ticket_id = str(context.get("active_ticket_id") or "").strip() or None
        recent_ticket_ids = [
            str(item).strip()
            for item in context.get("recent_ticket_ids", [])
            if str(item).strip()
        ]
        if active_ticket_id and active_ticket_id != normalized_ticket_id:
            recent_ticket_ids.insert(0, active_ticket_id)
        recent_ticket_ids = cls._dedupe_ticket_ids(
            [item for item in recent_ticket_ids if item != normalized_ticket_id],
            limit=_DEFAULT_RECENT_LIMIT,
        )
        context["active_ticket_id"] = normalized_ticket_id
        context["recent_ticket_ids"] = recent_ticket_ids

        incoming_mode = str(metadata.get("session_mode") or "").strip()
        if incoming_mode:
            context["session_mode"] = incoming_mode
        elif recent_ticket_ids:
            context["session_mode"] = "multi_issue"
        else:
            context["session_mode"] = "single_issue"

        incoming_intent = str(metadata.get("last_intent") or "").strip()
        if incoming_intent:
            context["last_intent"] = incoming_intent

        context["updated_at"] = datetime.now(UTC).isoformat()
        updated = dict(metadata)
        updated[_SESSION_CONTEXT_KEY] = context
        return updated

    @classmethod
    def _normalize_session_context(
        cls,
        raw_context: Any,
        *,
        fallback_ticket_id: str | None = None,
    ) -> dict[str, Any]:
        raw = raw_context if isinstance(raw_context, dict) else {}
        active_ticket_id = str(raw.get("active_ticket_id") or "").strip() or None
        if not active_ticket_id and fallback_ticket_id:
            normalized_fallback = str(fallback_ticket_id).strip()
            active_ticket_id = normalized_fallback or None
        recent_ticket_ids = cls._dedupe_ticket_ids(
            [
                str(item).strip()
                for item in raw.get("recent_ticket_ids", [])
                if str(item).strip()
            ],
            limit=_DEFAULT_RECENT_LIMIT,
        )
        if active_ticket_id:
            recent_ticket_ids = [item for item in recent_ticket_ids if item != active_ticket_id]
        session_mode = str(raw.get("session_mode") or "").strip()
        if not session_mode:
            session_mode = "multi_issue" if recent_ticket_ids else "single_issue"
        last_intent = str(raw.get("last_intent") or "").strip() or None
        updated_at = str(raw.get("updated_at") or "").strip() or None
        return {
            "active_ticket_id": active_ticket_id,
            "recent_ticket_ids": recent_ticket_ids,
            "session_mode": session_mode,
            "last_intent": last_intent,
            "updated_at": updated_at,
        }

    @staticmethod
    def _dedupe_ticket_ids(ticket_ids: list[str], *, limit: int) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for raw_ticket_id in ticket_ids:
            ticket_id = str(raw_ticket_id).strip()
            if not ticket_id or ticket_id in seen:
                continue
            deduped.append(ticket_id)
            seen.add(ticket_id)
            if len(deduped) >= limit:
                break
        return deduped
