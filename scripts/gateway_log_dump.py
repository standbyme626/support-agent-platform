from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config
from core.trace_logger import JsonTraceLogger


def main() -> int:
    parser = argparse.ArgumentParser(description="Print recent gateway traces")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--limit", default=20, type=int, help="Maximum events to print")
    args = parser.parse_args()

    app_config = load_app_config(args.env)
    logger = JsonTraceLogger(Path(app_config.gateway.log_path))

    for event in logger.read_recent(limit=args.limit):
        print(json.dumps(event, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
