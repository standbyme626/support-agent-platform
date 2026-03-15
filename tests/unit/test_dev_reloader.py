from __future__ import annotations

import time
from pathlib import Path

from scripts.dev_reloader import (
    build_default_watch_roots,
    build_file_snapshot,
    detect_changed_paths,
)


def test_build_default_watch_roots_only_includes_existing_paths(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / ".env").write_text("KEY=value\n", encoding="utf-8")

    roots = build_default_watch_roots(tmp_path)
    paths = {path.relative_to(tmp_path).as_posix() for path in roots}

    assert "app" in paths
    assert "scripts" in paths
    assert "pyproject.toml" in paths
    assert ".env" in paths
    assert "core" not in paths


def test_build_file_snapshot_tracks_code_and_env_files(tmp_path: Path) -> None:
    watch_dir = tmp_path / "scripts"
    watch_dir.mkdir()
    (watch_dir / "service.py").write_text("print('ok')\n", encoding="utf-8")
    (watch_dir / "notes.txt").write_text("ignore\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\n", encoding="utf-8")

    snapshot = build_file_snapshot([watch_dir, env_file])
    tracked_names = {Path(path).name for path in snapshot}

    assert "service.py" in tracked_names
    assert ".env" in tracked_names
    assert "notes.txt" not in tracked_names


def test_detect_changed_paths_on_file_modify(tmp_path: Path) -> None:
    target = tmp_path / "worker.py"
    target.write_text("value = 1\n", encoding="utf-8")
    before = build_file_snapshot([tmp_path])

    time.sleep(0.01)
    target.write_text("value = 2\n", encoding="utf-8")
    after = build_file_snapshot([tmp_path])
    changed = detect_changed_paths(before, after)

    assert any(path.endswith("worker.py") for path in changed)
