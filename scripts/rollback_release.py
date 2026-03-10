from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import load_app_config
from scripts.release_state import load_state, save_state


def rollback_release(
    *,
    environment: str | None,
    state_root: Path | None = None,
) -> dict[str, Any]:
    app_config = load_app_config(environment)
    env_name = app_config.environment
    state = load_state(env_name, state_root=state_root)
    active_release = state.get("active_release")
    commands = _commands(env_name)

    if not isinstance(active_release, dict):
        return {
            "status": "failed",
            "reason": "active_release_missing",
            "environment": env_name,
            "commands": commands,
            "diagnostics": {"state": state},
        }

    backups = active_release.get("backups")
    if not isinstance(backups, list):
        return {
            "status": "failed",
            "reason": "invalid_backup_metadata",
            "environment": env_name,
            "commands": commands,
            "diagnostics": {"active_release": active_release},
        }

    missing_snapshots: list[str] = []
    restored_paths: list[str] = []
    for item in backups:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("copied")):
            continue
        snapshot_path = Path(str(item.get("snapshot_path", "")))
        target_path = Path(str(item.get("target_path", "")))
        if not snapshot_path.exists():
            missing_snapshots.append(str(snapshot_path))
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot_path, target_path)
        restored_paths.append(str(target_path))

    if missing_snapshots:
        return {
            "status": "failed",
            "reason": "snapshot_missing",
            "environment": env_name,
            "commands": commands,
            "diagnostics": {
                "missing_snapshots": missing_snapshots,
                "restored_paths": restored_paths,
            },
        }

    previous_release = state.get("previous_release")
    history = state.get("history")
    if not isinstance(history, list):
        history = []
    rollback_time = datetime.now(UTC).isoformat()
    history.append(
        {
            "event": "rollback",
            "release_id": active_release.get("release_id"),
            "at": rollback_time,
        }
    )
    state["active_release"] = previous_release if isinstance(previous_release, dict) else None
    state["previous_release"] = None
    state["history"] = history[-30:]
    state["last_rollback"] = {
        "rolled_back_release_id": active_release.get("release_id"),
        "rolled_back_at": rollback_time,
        "restored_paths": restored_paths,
    }
    state_path = save_state(env_name, state_root=state_root, state=state)

    return {
        "status": "ok",
        "environment": env_name,
        "rolled_back_release_id": active_release.get("release_id"),
        "state_file": str(state_path),
        "restored_paths": restored_paths,
        "commands": commands,
    }


def _commands(environment: str) -> dict[str, str]:
    return {
        "redeploy": f"python -m scripts.deploy_release --env {environment}",
        "verify": f"python -m scripts.verify_release --env {environment}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback latest release from snapshot")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument(
        "--state-root",
        default=None,
        help="Optional release state root directory",
    )
    args = parser.parse_args()

    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else None
    result = rollback_release(environment=args.env, state_root=state_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
