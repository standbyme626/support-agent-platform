from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class MigrationManager:
    def __init__(self, sqlite_path: Path, migrations_dir: Path) -> None:
        self._sqlite_path = sqlite_path
        self._migrations_dir = migrations_dir
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_migrations_table()

    def apply_all(self) -> list[str]:
        applied = self._applied_migrations()
        applied_now: list[str] = []

        for migration_id in self._ordered_migration_ids():
            if migration_id in applied:
                continue

            up_sql = self._read_sql(migration_id, suffix="up")
            with self._connect() as conn:
                conn.executescript(up_sql)
                conn.execute(
                    "INSERT INTO schema_migrations(migration_id, applied_at) VALUES(?, ?)",
                    (migration_id, datetime.now(UTC).isoformat()),
                )
                conn.commit()
            applied_now.append(migration_id)

        return applied_now

    def rollback_last(self) -> str | None:
        last = self._latest_applied_migration()
        if last is None:
            return None

        down_sql = self._read_sql(last, suffix="down")
        with self._connect() as conn:
            conn.executescript(down_sql)
            conn.execute("DELETE FROM schema_migrations WHERE migration_id = ?", (last,))
            conn.commit()
        return last

    def applied_migrations(self) -> list[str]:
        return sorted(self._applied_migrations())

    def _ensure_migrations_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_id TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _ordered_migration_ids(self) -> list[str]:
        ids: list[str] = []
        for path in sorted(self._migrations_dir.glob("*.up.sql")):
            ids.append(path.name.replace(".up.sql", ""))
        return ids

    def _applied_migrations(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT migration_id FROM schema_migrations").fetchall()
        return {row[0] for row in rows}

    def _latest_applied_migration(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT migration_id FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def _read_sql(self, migration_id: str, *, suffix: str) -> str:
        path = self._migrations_dir / f"{migration_id}.{suffix}.sql"
        if not path.exists():
            raise FileNotFoundError(f"Migration file missing: {path}")
        return path.read_text(encoding="utf-8")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._sqlite_path)
