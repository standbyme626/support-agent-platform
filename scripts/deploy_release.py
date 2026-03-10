from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import load_app_config
from scripts.healthcheck import run_healthcheck
from scripts.release_state import (
    environment_dir,
    load_state,
    save_state,
)


def deploy_release(
    *,
    environment: str | None,
    state_root: Path | None = None,
) -> dict[str, Any]:
    app_config = load_app_config(environment)
    env_name = app_config.environment
    precheck = run_healthcheck(env_name)
    commands = _commands(env_name)

    if precheck.get("status") == "error":
        return {
            "status": "failed",
            "reason": "precheck_failed",
            "environment": env_name,
            "commands": commands,
            "diagnostics": {"healthcheck": precheck},
        }

    release_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    release_time = datetime.now(UTC).isoformat()
    env_dir = environment_dir(env_name, state_root=state_root)
    snapshot_dir = env_dir / "snapshots" / release_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    backups = _snapshot_runtime_files(
        snapshot_dir=snapshot_dir,
        sqlite_path=Path(app_config.storage.sqlite_path),
        log_path=Path(app_config.gateway.log_path),
    )

    current_state = load_state(env_name, state_root=state_root)
    previous_release = current_state.get("active_release")
    active_release: dict[str, Any] = {
        "release_id": release_id,
        "deployed_at": release_time,
        "environment": env_name,
        "snapshot_dir": str(snapshot_dir),
        "backups": backups,
        "verify_command": commands["verify"],
        "rollback_command": commands["rollback"],
    }
    history = current_state.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "event": "deploy",
            "release_id": release_id,
            "at": release_time,
        }
    )
    state: dict[str, Any] = {
        "environment": env_name,
        "active_release": active_release,
        "previous_release": previous_release if isinstance(previous_release, dict) else None,
        "history": history[-30:],
    }
    state_path = save_state(env_name, state_root=state_root, state=state)

    return {
        "status": "ok",
        "environment": env_name,
        "release_id": release_id,
        "state_file": str(state_path),
        "snapshot_dir": str(snapshot_dir),
        "backups": backups,
        "commands": commands,
        "diagnostics": {"precheck_status": precheck.get("status"), "healthcheck": precheck},
    }


def _snapshot_runtime_files(
    *,
    snapshot_dir: Path,
    sqlite_path: Path,
    log_path: Path,
) -> list[dict[str, object]]:
    targets = {
        "sqlite_db": sqlite_path,
        "gateway_log": log_path,
    }
    backups: list[dict[str, object]] = []
    for name, target in targets.items():
        snapshot_path = snapshot_dir / f"{name}{target.suffix or '.bak'}"
        copied = False
        if target.exists() and target.is_file():
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, snapshot_path)
            copied = True
        backups.append(
            {
                "name": name,
                "target_path": str(target),
                "snapshot_path": str(snapshot_path),
                "copied": copied,
            }
        )
    return backups


def _commands(environment: str) -> dict[str, str]:
    return {
        "precheck": f"python scripts/healthcheck.py --env {environment}",
        "verify": f"python -m scripts.verify_release --env {environment} --require-active-release",
        "rollback": f"python -m scripts.rollback_release --env {environment}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy release with precheck and rollback snapshot"
    )
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument(
        "--state-root",
        default=None,
        help="Optional release state root directory",
    )
    args = parser.parse_args()

    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else None
    result = deploy_release(environment=args.env, state_root=state_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
