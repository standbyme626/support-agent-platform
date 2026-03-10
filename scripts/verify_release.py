from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from config import load_app_config
from scripts.gateway_status import collect_status
from scripts.healthcheck import run_healthcheck
from scripts.release_state import load_state, state_file_path


def verify_release(
    *,
    environment: str | None,
    state_root: Path | None = None,
    require_active_release: bool = False,
) -> dict[str, Any]:
    app_config = load_app_config(environment)
    env_name = app_config.environment
    health = run_healthcheck(env_name)
    gateway = collect_status(env_name)
    state = load_state(env_name, state_root=state_root)
    active_release = state.get("active_release")
    errors: list[str] = []

    if health.get("status") == "error":
        errors.append("healthcheck_failed")
    if require_active_release and not isinstance(active_release, dict):
        errors.append("active_release_missing")

    commands = _commands(env_name)
    diagnostics: dict[str, object] = {
        "healthcheck": health,
        "gateway_status": gateway,
        "state_file": str(state_file_path(env_name, state_root=state_root)),
    }
    if isinstance(active_release, dict):
        diagnostics["active_release"] = {
            "release_id": active_release.get("release_id"),
            "deployed_at": active_release.get("deployed_at"),
            "snapshot_dir": active_release.get("snapshot_dir"),
        }

    return {
        "status": "ok" if not errors else "failed",
        "environment": env_name,
        "errors": errors,
        "commands": commands,
        "diagnostics": diagnostics,
    }


def _commands(environment: str) -> dict[str, str]:
    return {
        "healthcheck": f"python scripts/healthcheck.py --env {environment}",
        "gateway_status": f"python scripts/gateway_status.py --env {environment}",
        "rollback": f"python -m scripts.rollback_release --env {environment}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deployment status for one environment")
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument(
        "--state-root",
        default=None,
        help="Optional release state root directory",
    )
    parser.add_argument(
        "--require-active-release",
        action="store_true",
        help="Require active release to exist in state file",
    )
    args = parser.parse_args()

    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else None
    result = verify_release(
        environment=args.env,
        state_root=state_root,
        require_active_release=args.require_active_release,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
