from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .migration_manager import MigrationManager
from .models import (
    HandoffState,
    LifecycleStage,
    RiskLevel,
    Ticket,
    TicketEvent,
    TicketPriority,
    TicketStatus,
)


class TicketRepository:
    def __init__(self, sqlite_path: Path, migrations_dir: Path | None = None) -> None:
        self._sqlite_path = sqlite_path
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        default_migrations = Path(__file__).resolve().parent / "migrations"
        self._migration_manager = MigrationManager(
            sqlite_path, migrations_dir or default_migrations
        )

    def apply_migrations(self) -> list[str]:
        return self._migration_manager.apply_all()

    def rollback_last_migration(self) -> str | None:
        return self._migration_manager.rollback_last()

    def applied_migrations(self) -> list[str]:
        return self._migration_manager.applied_migrations()

    def create_ticket(
        self,
        *,
        channel: str,
        session_id: str,
        thread_id: str,
        title: str,
        latest_message: str,
        intent: str,
        priority: TicketPriority,
        queue: str,
        customer_id: str | None = None,
        assignee: str | None = None,
        status: TicketStatus = "open",
        needs_handoff: bool = False,
        inbox: str = "default",
        lifecycle_stage: LifecycleStage = "intake",
        first_response_due_at: datetime | None = None,
        resolution_due_at: datetime | None = None,
        escalated_at: datetime | None = None,
        resolved_at: datetime | None = None,
        closed_at: datetime | None = None,
        resolution_note: str | None = None,
        resolution_code: str | None = None,
        close_reason: str | None = None,
        source_channel: str | None = None,
        handoff_state: str = "none",
        last_agent_action: str | None = None,
        risk_level: str = "medium",
        metadata: dict[str, Any] | None = None,
        ticket_id: str | None = None,
    ) -> Ticket:
        created_at = datetime.now(UTC)
        generated_ticket_id = ticket_id or self._new_ticket_id()
        payload = {
            "ticket_id": generated_ticket_id,
            "channel": channel,
            "session_id": session_id,
            "thread_id": thread_id,
            "customer_id": customer_id,
            "title": title,
            "latest_message": latest_message,
            "intent": intent,
            "priority": priority,
            "status": status,
            "queue": queue,
            "assignee": assignee,
            "needs_handoff": int(needs_handoff),
            "inbox": inbox,
            "lifecycle_stage": lifecycle_stage,
            "first_response_due_at": self._to_db_datetime(first_response_due_at),
            "resolution_due_at": self._to_db_datetime(resolution_due_at),
            "escalated_at": self._to_db_datetime(escalated_at),
            "resolved_at": self._to_db_datetime(resolved_at),
            "closed_at": self._to_db_datetime(closed_at),
            "resolution_note": resolution_note,
            "resolution_code": resolution_code,
            "close_reason": close_reason,
            "source_channel": source_channel or channel,
            "handoff_state": handoff_state,
            "last_agent_action": last_agent_action,
            "risk_level": risk_level,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tickets(
                  ticket_id, channel, session_id, thread_id, customer_id,
                  title, latest_message, intent, priority, status,
                  queue, assignee, needs_handoff, inbox, lifecycle_stage,
                  first_response_due_at, resolution_due_at, escalated_at, resolved_at,
                  closed_at, resolution_note, resolution_code, close_reason,
                  source_channel, handoff_state, last_agent_action, risk_level,
                  metadata_json, created_at, updated_at
                )
                VALUES(
                  :ticket_id, :channel, :session_id, :thread_id, :customer_id,
                  :title, :latest_message, :intent, :priority, :status,
                  :queue, :assignee, :needs_handoff, :inbox, :lifecycle_stage,
                  :first_response_due_at, :resolution_due_at, :escalated_at, :resolved_at,
                  :closed_at, :resolution_note, :resolution_code, :close_reason,
                  :source_channel, :handoff_state, :last_agent_action, :risk_level,
                  :metadata_json, :created_at, :updated_at
                )
                """,
                payload,
            )
            conn.commit()

        created = self.get_ticket(generated_ticket_id)
        if created is None:
            raise RuntimeError(f"Failed to load created ticket {generated_ticket_id}")
        return created

    def update_ticket(self, ticket_id: str, updates: dict[str, Any]) -> Ticket:
        allowed_fields = {
            "title",
            "latest_message",
            "intent",
            "priority",
            "status",
            "queue",
            "assignee",
            "needs_handoff",
            "inbox",
            "lifecycle_stage",
            "first_response_due_at",
            "resolution_due_at",
            "escalated_at",
            "resolved_at",
            "closed_at",
            "resolution_note",
            "resolution_code",
            "close_reason",
            "source_channel",
            "handoff_state",
            "last_agent_action",
            "risk_level",
            "metadata",
        }

        unknown = set(updates) - allowed_fields
        if unknown:
            raise ValueError(f"Unsupported update fields: {sorted(unknown)}")

        db_updates: dict[str, Any] = {}
        datetime_fields = {
            "first_response_due_at",
            "resolution_due_at",
            "escalated_at",
            "resolved_at",
            "closed_at",
        }
        for key, value in updates.items():
            if key == "metadata":
                db_updates["metadata_json"] = json.dumps(
                    value or {}, ensure_ascii=False, sort_keys=True
                )
            elif key == "needs_handoff":
                db_updates[key] = int(bool(value))
            elif key in datetime_fields:
                db_updates[key] = self._to_db_datetime(value)
            else:
                db_updates[key] = value

        db_updates["updated_at"] = datetime.now(UTC).isoformat()
        assignments = ", ".join(f"{field} = :{field}" for field in db_updates.keys())

        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE tickets SET {assignments} WHERE ticket_id = :ticket_id",
                {**db_updates, "ticket_id": ticket_id},
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Ticket not found: {ticket_id}")
            conn.commit()

        updated = self.get_ticket(ticket_id)
        if updated is None:
            raise RuntimeError(f"Failed to load updated ticket {ticket_id}")
        return updated

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_ticket(row)

    def list_tickets(
        self,
        *,
        status: str | None = None,
        queue: str | None = None,
        assignee: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        conditions: list[str] = []
        params: list[Any] = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if queue is not None:
            conditions.append("queue = ?")
            params.append(queue)
        if assignee is not None:
            conditions.append("assignee = ?")
            params.append(assignee)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT * FROM tickets
            {where_clause}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_ticket(row) for row in rows]

    def append_event(
        self,
        *,
        ticket_id: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> TicketEvent:
        created_at = datetime.now(UTC)
        generated_event_id = event_id or f"evt_{uuid.uuid4().hex[:12]}"
        body = payload or {}
        idempotency_key = str(body.get("idempotency_key") or "").strip()
        if idempotency_key:
            deduped = self.find_event_by_idempotency_key(
                ticket_id=ticket_id,
                event_type=event_type,
                idempotency_key=idempotency_key,
            )
            if deduped is not None:
                return deduped

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ticket_events(
                  event_id, ticket_id, event_type, actor_type, actor_id, payload_json, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generated_event_id,
                    ticket_id,
                    event_type,
                    actor_type,
                    actor_id,
                    json.dumps(
                        body,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=self._json_default,
                    ),
                    created_at.isoformat(),
                ),
            )
            conn.commit()

        event = self.get_event(generated_event_id)
        if event is None:
            raise RuntimeError(f"Failed to load created event {generated_event_id}")
        return event

    def find_ticket_by_idempotency_key(self, idempotency_key: str) -> Ticket | None:
        normalized_key = idempotency_key.strip()
        if not normalized_key:
            return None

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM tickets
                ORDER BY updated_at DESC
                LIMIT 500
                """
            ).fetchall()

        for row in rows:
            metadata = json.loads(str(row["metadata_json"]))
            if str(metadata.get("idempotency_key") or "").strip() == normalized_key:
                return self._row_to_ticket(row)
        return None

    def find_event_by_idempotency_key(
        self,
        *,
        ticket_id: str,
        event_type: str | None,
        idempotency_key: str,
    ) -> TicketEvent | None:
        normalized_key = idempotency_key.strip()
        if not normalized_key:
            return None

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM ticket_events
                WHERE ticket_id = ?
                ORDER BY created_at DESC
                LIMIT 500
                """,
                (ticket_id,),
            ).fetchall()

        for row in rows:
            if event_type is not None and str(row["event_type"]) != event_type:
                continue
            payload = json.loads(str(row["payload_json"]))
            if str(payload.get("idempotency_key") or "").strip() == normalized_key:
                return self._row_to_event(row)
        return None

    def get_event(self, event_id: str) -> TicketEvent | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ticket_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_event(row)

    def list_events(self, ticket_id: str, *, limit: int = 200) -> list[TicketEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ticket_events
                WHERE ticket_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (ticket_id, limit),
            ).fetchall()

        return [self._row_to_event(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _new_ticket_id() -> str:
        return f"TCK-{uuid.uuid4().hex[:10].upper()}"

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _row_to_ticket(row: sqlite3.Row) -> Ticket:
        row_keys = set(row.keys())
        priority = str(row["priority"])
        status = str(row["status"])
        lifecycle_stage = str(row["lifecycle_stage"]) if "lifecycle_stage" in row_keys else "intake"
        if priority not in {"P1", "P2", "P3", "P4"}:
            raise ValueError(f"Invalid priority in DB: {priority}")
        if status not in {"open", "pending", "escalated", "handoff", "resolved", "closed"}:
            raise ValueError(f"Invalid status in DB: {status}")
        if lifecycle_stage not in {
            "intake",
            "classified",
            "retrieved",
            "drafted",
            "awaiting_human",
            "resolved",
            "closed",
        }:
            raise ValueError(f"Invalid lifecycle_stage in DB: {lifecycle_stage}")

        return Ticket(
            ticket_id=str(row["ticket_id"]),
            channel=str(row["channel"]),
            session_id=str(row["session_id"]),
            thread_id=str(row["thread_id"]),
            customer_id=row["customer_id"],
            title=str(row["title"]),
            latest_message=str(row["latest_message"]),
            intent=str(row["intent"]),
            priority=cast(TicketPriority, priority),
            status=cast(TicketStatus, status),
            queue=str(row["queue"]),
            assignee=row["assignee"],
            needs_handoff=bool(row["needs_handoff"]),
            inbox=str(row["inbox"]) if "inbox" in row_keys else "default",
            lifecycle_stage=cast(LifecycleStage, lifecycle_stage),
            first_response_due_at=TicketRepository._parse_optional_datetime(
                row["first_response_due_at"] if "first_response_due_at" in row_keys else None
            ),
            resolution_due_at=TicketRepository._parse_optional_datetime(
                row["resolution_due_at"] if "resolution_due_at" in row_keys else None
            ),
            escalated_at=TicketRepository._parse_optional_datetime(
                row["escalated_at"] if "escalated_at" in row_keys else None
            ),
            resolved_at=TicketRepository._parse_optional_datetime(
                row["resolved_at"] if "resolved_at" in row_keys else None
            ),
            closed_at=TicketRepository._parse_optional_datetime(
                row["closed_at"] if "closed_at" in row_keys else None
            ),
            resolution_note=(
                str(row["resolution_note"])
                if "resolution_note" in row_keys and row["resolution_note"] is not None
                else None
            ),
            resolution_code=(
                str(row["resolution_code"])
                if "resolution_code" in row_keys and row["resolution_code"] is not None
                else None
            ),
            close_reason=(
                str(row["close_reason"])
                if "close_reason" in row_keys and row["close_reason"] is not None
                else None
            ),
            source_channel=(
                str(row["source_channel"])
                if "source_channel" in row_keys and row["source_channel"] is not None
                else str(row["channel"])
            ),
            handoff_state=cast(
                HandoffState,
                str(row["handoff_state"])
                if "handoff_state" in row_keys and row["handoff_state"] is not None
                else "none",
            ),
            last_agent_action=(
                str(row["last_agent_action"])
                if "last_agent_action" in row_keys and row["last_agent_action"] is not None
                else None
            ),
            risk_level=cast(
                RiskLevel,
                str(row["risk_level"])
                if "risk_level" in row_keys and row["risk_level"] is not None
                else "medium",
            ),
            metadata=json.loads(str(row["metadata_json"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> TicketEvent:
        return TicketEvent(
            event_id=str(row["event_id"]),
            ticket_id=str(row["ticket_id"]),
            event_type=str(row["event_type"]),
            actor_type=str(row["actor_type"]),
            actor_id=str(row["actor_id"]),
            payload=json.loads(str(row["payload_json"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    @staticmethod
    def _parse_optional_datetime(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        return datetime.fromisoformat(str(value))

    @staticmethod
    def _to_db_datetime(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return value.isoformat()
