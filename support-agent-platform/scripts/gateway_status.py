from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config
from core.trace_logger import JsonTraceLogger
from openclaw_adapter.session_mapper import SessionMapper


def collect_status(environment: str | None = None) -> dict[str, object]:
    app_config = load_app_config(environment)
    mapper = SessionMapper(Path(app_config.storage.sqlite_path))
    logger = JsonTraceLogger(Path(app_config.gateway.log_path))

    return {
        "environment": app_config.environment,
        "gateway": app_config.gateway.name,
        "sqlite_path": str(app_config.storage.sqlite_path),
        "session_bindings": mapper.count(),
        "log_path": str(logger.path),
        "recent_events": logger.read_recent(limit=5),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Show gateway status and recent traces")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    args = parser.parse_args()

    print(json.dumps(collect_status(args.env), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
