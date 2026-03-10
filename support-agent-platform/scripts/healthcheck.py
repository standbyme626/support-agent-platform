from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from config import load_app_config
from openclaw_adapter.session_mapper import SessionMapper
from storage.ticket_repository import TicketRepository


def run_healthcheck(environment: str | None = None) -> dict[str, object]:
    started_at = datetime.now(UTC)
    checks: dict[str, dict[str, object]] = {}

    try:
        app_config = load_app_config(environment)
        checks["config"] = {"ok": True, "environment": app_config.environment}
    except Exception as exc:
        return {
            "status": "error",
            "checked_at": started_at.isoformat(),
            "checks": {"config": {"ok": False, "error": str(exc)}},
        }

    sqlite_path = Path(app_config.storage.sqlite_path)

    try:
        repo = TicketRepository(sqlite_path)
        applied = repo.apply_migrations()
        checks["storage"] = {
            "ok": True,
            "sqlite_path": str(sqlite_path),
            "applied_migrations": repo.applied_migrations(),
            "applied_now": applied,
        }
    except Exception as exc:
        checks["storage"] = {"ok": False, "error": str(exc)}

    try:
        mapper = SessionMapper(sqlite_path)
        checks["session_mapper"] = {"ok": True, "bindings": mapper.count()}
    except Exception as exc:
        checks["session_mapper"] = {"ok": False, "error": str(exc)}

    status = "ok" if all(bool(item.get("ok")) for item in checks.values()) else "degraded"
    finished_at = datetime.now(UTC)

    return {
        "status": status,
        "checked_at": finished_at.isoformat(),
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run support-agent-platform health checks")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    args = parser.parse_args()

    report = run_healthcheck(args.env)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"ok", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
