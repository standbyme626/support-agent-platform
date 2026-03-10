from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_RELEASE_STATE_ROOT = Path(__file__).resolve().parents[1] / "storage" / "releases"


def resolve_state_root(state_root: Path | None) -> Path:
    return (state_root or DEFAULT_RELEASE_STATE_ROOT).resolve()


def environment_dir(environment: str, *, state_root: Path | None) -> Path:
    return resolve_state_root(state_root) / environment


def state_file_path(environment: str, *, state_root: Path | None) -> Path:
    return environment_dir(environment, state_root=state_root) / "state.json"


def load_state(environment: str, *, state_root: Path | None) -> dict[str, Any]:
    state_path = state_file_path(environment, state_root=state_root)
    if not state_path.exists():
        return {}
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}


def save_state(environment: str, *, state_root: Path | None, state: dict[str, Any]) -> Path:
    env_dir = environment_dir(environment, state_root=state_root)
    env_dir.mkdir(parents=True, exist_ok=True)
    state_path = env_dir / "state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path
